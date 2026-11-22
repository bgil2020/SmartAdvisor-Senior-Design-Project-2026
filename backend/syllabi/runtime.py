"""Explicit headed Chromium acquisition runtime for exact approved mappings."""
from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import Future
from pathlib import Path
from typing import Any

from backend.course_descriptions.models import utc_now
from backend.acquisition_budget import claim_test_budget
from backend.session_evidence import attach_provenance
from .parser import SyllabusParseError, parse_rendered_syllabus
from .browser_probe import BrowserProbeLimits, probe_browser_session
from .playwright_driver import BrowserExecutableConfigurationError, PlaywrightSession
from .storage import validate_record

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "data" / "syllabi" / "sample-manifest.json"
_browser_slot = threading.BoundedSemaphore(1)
_inflight_lock = threading.Lock()
_inflight: dict[tuple[str, str, str], Future] = {}


def _mapping(course_code: str, term_id: str, section: str, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any] | None:
    documents = json.loads(manifest_path.read_text(encoding="utf-8")).get("documents", [])
    wanted = (course_code.replace(" ", "").upper(), str(term_id), str(section))
    matches = [item for item in documents if (str(item.get("course_code", "")).replace(" ", "").upper(), str(item.get("term_id")), str(item.get("section"))) == wanted]
    return matches[0] if len(matches) == 1 else None


def acquire_exact_syllabus(course_code: str, term_id: str, section: str) -> dict[str, Any]:
    """One logical headed navigation; never switches modes or invents a URL."""
    if os.getenv("SYLLABUS_ACQUISITION_ENABLED", "false").casefold() != "true":
        return {"status": "disabled", "record": None, "duration_ms": 0, "cleanup": "not_started"}
    if os.getenv("ACQUISITION_BROWSER_MODE", "").casefold() != "headed":
        return {"status": "headed_mode_not_selected", "record": None, "duration_ms": 0, "cleanup": "not_started"}
    mapping = _mapping(course_code, term_id, section)
    if not mapping:
        return {"status": "no_exact_approved_mapping", "record": None, "duration_ms": 0, "cleanup": "not_started"}
    key = (course_code.replace(" ", "").upper(), str(term_id), str(section))
    with _inflight_lock:
        future = _inflight.get(key)
        owner = future is None
        if owner:
            future = Future()
            _inflight[key] = future
    if not owner:
        return future.result(timeout=float(os.getenv("ACQUISITION_TIMEOUT_SECONDS", "25")) + 5)
    try:
        budget = claim_test_budget("syllabus")
        if not budget["allowed"]:
            result = {
                "status": "acquisition_budget_exhausted", "record": None,
                "request_count": 0, "duration_ms": 0, "cleanup": "not_started",
                "test_budget": budget,
            }
        else:
            result = _run_mapping(mapping)
            if budget["enforced"]:
                result["test_budget"] = budget
        future.set_result(result)
        return result
    except BaseException as exc:
        safe = {"status": "runtime_error", "record": None, "error_type": type(exc).__name__, "duration_ms": 0, "cleanup": "attempted"}
        if isinstance(exc, BrowserExecutableConfigurationError):
            safe["diagnostic"] = exc.code
        future.set_result(safe)
        return safe
    finally:
        with _inflight_lock:
            _inflight.pop(key, None)


def _run_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    timeout_seconds = max(1.0, float(os.getenv("ACQUISITION_TIMEOUT_SECONDS", "20")))
    maximum_html_bytes = max(1024, int(os.getenv("ACQUISITION_MAX_RENDERED_HTML_BYTES", str(2 * 1024 * 1024))))
    readiness_text = os.getenv("ACQUISITION_READINESS_TEXT", "Course Evaluation Method")
    started = time.monotonic()
    with _browser_slot:
        session = PlaywrightSession(
            document_id=str(mapping["source_document_id"]),
            readiness_text=readiness_text,
            visible=True,
            deadline_seconds=timeout_seconds,
        )
        probe = probe_browser_session(
            session,
            mapping["view_url"],
            limits=BrowserProbeLimits(max_rendered_html_bytes=maximum_html_bytes),
        )
        probe_status = str(probe.get("status", "incomplete_extraction"))
        observations = {
            **{key: value for key, value in probe.items() if key != "status"},
            "probe_status": probe_status,
            "cleanup": "completed",
        }
        if probe_status != "anonymous_full_document":
            return {**observations, "status": probe_status, "record": None, "request_count": probe["logical_navigations"], "duration_ms": round((time.monotonic() - started) * 1000)}
        candidate_status, record = _parse_and_validate_candidate(session.last_html, mapping, session.final_url)
        if candidate_status != "acquired":
            return {**observations, "status": candidate_status, "record": None, "request_count": probe["logical_navigations"], "duration_ms": round((time.monotonic() - started) * 1000)}
        return {**observations, "status": "acquired", "record": attach_provenance(record), "request_count": probe["logical_navigations"], "duration_ms": round((time.monotonic() - started) * 1000)}


def _parse_and_validate_candidate(html: str, mapping: dict[str, Any], source_url: str) -> tuple[str, dict[str, Any] | None]:
    """Shared parser/validator boundary for live and local synthetic acquisition."""
    try:
        record = parse_rendered_syllabus(
            html, course_code=mapping["course_code"], term_id=mapping["term_id"], term_name=mapping["term_name"],
            section=mapping["section"], source_document_id=mapping["source_document_id"], source_url=source_url,
            fetched_at=utc_now(), raw_evidence_ref="session-memory:rendered-html", instructor=mapping.get("instructor"), render_complete=True,
        )
    except SyllabusParseError as exc:
        return exc.code, None
    if validate_record(record):
        return "candidate_rejected", None
    return "acquired", record


def synthetic_smoke(url: str) -> dict[str, Any]:
    """Run a complete offline acquisition through the production runtime path."""
    if os.getenv("RENDER_STARTUP_BROWSER_SMOKE", "false").casefold() != "true":
        return {"status": "disabled"}
    allowed = {"http://127.0.0.1:8765/synthetic.html", "http://localhost:8765/synthetic.html"}
    if url not in allowed:
        return {"status": "rejected_url"}
    mapping = {
        "course_code": "COP4331",
        "term_id": "202608",
        "term_name": "Fall 2026 1 Full Term",
        "section": "002",
        "instructor": "Synthetic Test Instructor",
        "source_document_id": "offline-runtime-smoke",
        "view_url": url,
    }
    timeout_seconds = max(1.0, float(os.getenv("ACQUISITION_TIMEOUT_SECONDS", "20")))
    maximum_html_bytes = max(1024, int(os.getenv("ACQUISITION_MAX_RENDERED_HTML_BYTES", str(2 * 1024 * 1024))))
    with _browser_slot:
        session = PlaywrightSession(
            document_id=str(mapping["source_document_id"]),
            readiness_text="Course Evaluation Method",
            visible=True,
            deadline_seconds=timeout_seconds,
        )
        probe = probe_browser_session(
            session,
            url,
            limits=BrowserProbeLimits(max_rendered_html_bytes=maximum_html_bytes),
        )
    candidate_status, record = _parse_and_validate_candidate(
        session.last_html,
        mapping,
        "https://fau.simplesyllabus.com/doc/offline-runtime-smoke/local-synthetic-document?mode=view",
    )
    record = record or {}
    source = record.get("source") if isinstance(record.get("source"), dict) else {}
    passed = (
        probe.get("status") == "anonymous_full_document"
        and candidate_status == "acquired"
        and record.get("course_code") == "COP4331"
        and (record.get("term_scope") or {}).get("term_id") == "202608"
        and (record.get("section_scope") or {}).get("section") == "002"
        and source.get("source_id") == "offline-runtime-smoke"
    )
    return {
        "status": "passed" if passed else "failed",
        "acquisition_status": candidate_status,
        "probe_status": probe.get("status"),
        "logical_navigations": probe.get("logical_navigations"),
        "actual_observed_responses": probe.get("actual_observed_responses"),
        "identity_validated": passed,
        "cleanup": "completed",
        "diagnostic": None,
    }
