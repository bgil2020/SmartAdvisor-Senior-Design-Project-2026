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
from .parser import SyllabusParseError, classify_browser_observation, parse_rendered_syllabus

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
    from playwright.sync_api import sync_playwright
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    timeout_ms = int(float(os.getenv("ACQUISITION_TIMEOUT_SECONDS", "20")) * 1000)
    started = time.monotonic()
    failed: list[dict[str, Any]] = []
    cleanup = "attempted"
    with _browser_slot:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False, args=["--disable-dev-shm-usage", "--no-sandbox"])
            context = browser.new_context()
            page = context.new_page()
            try:
                def observe(response: Any) -> None:
                    if response.status in {401, 403}:
                        failed.append({"status": response.status, "essential": response.url.startswith(mapping["view_url"].split("?", 1)[0])})
                page.on("response", observe)
                page.goto(mapping["view_url"], wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_selector("main, article, [data-syllabus-document]", state="attached", timeout=timeout_ms)
                html = page.content()
                final_url = page.url
                status = classify_browser_observation(html, final_url, failed_requests=failed)
                if status != "anonymous_full_document":
                    return {"status": status, "record": None, "duration_ms": round((time.monotonic() - started) * 1000), "cleanup": cleanup}
                record = parse_rendered_syllabus(
                    html, course_code=mapping["course_code"], term_id=mapping["term_id"], term_name=mapping["term_name"],
                    section=mapping["section"], source_document_id=mapping["source_document_id"], source_url=final_url,
                    fetched_at=utc_now(), raw_evidence_ref="session-memory:rendered-html", instructor=mapping.get("instructor"), render_complete=True,
                )
                return {"status": "acquired", "record": attach_provenance(record), "duration_ms": round((time.monotonic() - started) * 1000), "cleanup": cleanup}
            except SyllabusParseError as exc:
                return {"status": exc.code, "record": None, "duration_ms": round((time.monotonic() - started) * 1000), "cleanup": cleanup}
            except PlaywrightTimeoutError:
                return {"status": "timeout", "record": None, "duration_ms": round((time.monotonic() - started) * 1000), "cleanup": cleanup}
            finally:
                context.close()
                browser.close()


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
