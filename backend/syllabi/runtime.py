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
from backend.session_evidence import attach_provenance
from .parser import SyllabusParseError, parse_rendered_syllabus
from .browser_probe import BrowserProbeLimits, probe_browser_session
from .playwright_driver import PlaywrightSession

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
        result = _run_mapping(mapping)
        future.set_result(result)
        return result
    except BaseException as exc:
        safe = {"status": "runtime_error", "record": None, "error_type": type(exc).__name__, "duration_ms": 0, "cleanup": "attempted"}
        future.set_result(safe)
        return safe
    finally:
        with _inflight_lock:
            _inflight.pop(key, None)


def _run_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    timeout_seconds = max(1.0, float(os.getenv("ACQUISITION_TIMEOUT_SECONDS", "20")))
    maximum_html_bytes = max(1024, int(os.getenv("ACQUISITION_MAX_RENDERED_HTML_BYTES", str(2 * 1024 * 1024))))
    chrome = Path(os.getenv("ACQUISITION_CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe"))
    readiness_text = os.getenv("ACQUISITION_READINESS_TEXT", "Course Evaluation Method")
    started = time.monotonic()
    with _browser_slot:
        session = PlaywrightSession(
            chrome=chrome,
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
        observations = {**probe, "cleanup": "completed"}
        if probe["status"] != "anonymous_full_document":
            return {"status": probe["status"], "record": None, "duration_ms": round((time.monotonic() - started) * 1000), **observations}
        try:
            record = parse_rendered_syllabus(
                session.last_html, course_code=mapping["course_code"], term_id=mapping["term_id"], term_name=mapping["term_name"],
                section=mapping["section"], source_document_id=mapping["source_document_id"], source_url=session.final_url,
                fetched_at=utc_now(), raw_evidence_ref="session-memory:rendered-html", instructor=mapping.get("instructor"), render_complete=True,
            )
        except SyllabusParseError as exc:
            return {"status": exc.code, "record": None, "duration_ms": round((time.monotonic() - started) * 1000), **observations}
        return {"status": "acquired", "record": attach_provenance(record), "duration_ms": round((time.monotonic() - started) * 1000), **observations}


def synthetic_smoke(url: str) -> dict[str, Any]:
    """Bounded startup smoke for a fixed operator-supplied local URL only."""
    if os.getenv("RENDER_STARTUP_BROWSER_SMOKE", "false").casefold() != "true":
        return {"status": "disabled"}
    allowed = {"http://127.0.0.1:8765/synthetic.html", "http://localhost:8765/synthetic.html"}
    if url not in allowed:
        return {"status": "rejected_url"}
    from playwright.sync_api import sync_playwright
    with _browser_slot, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False, args=["--disable-dev-shm-usage", "--no-sandbox"])
        try:
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=5_000)
            return {"status": "passed" if page.locator("[data-smoke-ready]").count() == 1 else "incomplete"}
        finally:
            browser.close()
