"""One separately approved CAP4773 acquisition through the local chatbot UI.

Diagnostics exclude source/answer text, prompts, signatures, credentials, and
private data. Running this file requires a new explicit live-source approval.
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_URL = "http://127.0.0.1:14173"
BACKEND_URL = "http://127.0.0.1:18100"
EXPECTED_SCOPE = {"course_code": "CAP4773", "term_id": "202608", "section": "001"}
EXPECTED_DOCUMENT = "fjhz2vvga"
EXPECTED_URL = "https://fau.simplesyllabus.com/doc/fjhz2vvga/Fall-2026-1-Full-Term-CAP-4773-001-Intro-Data-Science-Analytics?mode=view"
CHROME_PATH = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
EVIDENCE_PATH = ROOT / "docs" / "acquisition-evidence" / "cap4773-live-acquisition-reuse-next.json"
SCREENSHOT_PATH = ROOT / "docs" / "acquisition-evidence" / "cap4773-live-ui-reuse-next-redacted.png"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sanitized_diagnostics(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Return bounded metadata without retaining raw source or secret values."""
    payload = payload or {}
    acquisition = payload.get("acquisition") if isinstance(payload.get("acquisition"), dict) else {}
    evidence = payload.get("acquired_evidence") if isinstance(payload.get("acquired_evidence"), list) else []
    citations = payload.get("citations") if isinstance(payload.get("citations"), list) else []
    record = evidence[0] if evidence and isinstance(evidence[0], dict) else {}
    source = record.get("source") if isinstance(record.get("source"), dict) else {}
    provenance = record.get("session_provenance") if isinstance(record.get("session_provenance"), dict) else {}
    citation = citations[0] if citations and isinstance(citations[0], dict) else {}
    return {
        "schema_version": "1.0",
        "attempt_label": "future-acquisition-and-evidence-reuse-requires-separate-approval",
        "conclusion": "in_progress",
        "tested_head": "0fca051c6b43108a8fc6d33a8566b26b19893c4f",
        "response": {
            "status": payload.get("status"),
            "response_code": payload.get("response_code"),
            "source_scope": payload.get("source_scope"),
            "generation_source": payload.get("generation_source"),
            "generation_fallback_used": payload.get("generation_fallback_used"),
        },
        "acquisition": {
            "final_status": acquisition.get("status"),
            "probe_status": acquisition.get("probe_status"),
            "additional_source_acquisitions": acquisition.get("additional_source_acquisitions"),
            "logical_navigations": acquisition.get("request_count"),
            "observed_browser_responses": acquisition.get("actual_observed_responses"),
            "essential_document_requests": acquisition.get("essential_document_requests"),
            "essential_document_failures": acquisition.get("essential_document_failures"),
            "access_denials": acquisition.get("access_denials"),
            "stop_reason": acquisition.get("stop_reason"),
            "duration_ms": acquisition.get("duration_ms"),
            "cleanup": acquisition.get("cleanup"),
            "limits": acquisition.get("limits") if isinstance(acquisition.get("limits"), dict) else None,
            "test_budget": acquisition.get("test_budget") if isinstance(acquisition.get("test_budget"), dict) else None,
            "session_evidence_submitted": acquisition.get("session_evidence_submitted"),
            "session_evidence_accepted": acquisition.get("session_evidence_accepted"),
            "session_evidence_matched": acquisition.get("session_evidence_matched"),
            "session_evidence_reused": acquisition.get("session_evidence_reused"),
        },
        "evidence": {
            "record_count": len(evidence),
            "record_category": record.get("record_category"),
            "course_code": record.get("course_code"),
            "term_id": (record.get("term_scope") or {}).get("term_id") if isinstance(record.get("term_scope"), dict) else None,
            "section": (record.get("section_scope") or {}).get("section") if isinstance(record.get("section_scope"), dict) else None,
            "source_document_id": source.get("source_id"),
            "source_url_matches_document": EXPECTED_DOCUMENT in str(source.get("url", "")),
            "record_id": record.get("record_id"),
            "content_sha256": record.get("content_sha256"),
            "document_character_count": len(str(record.get("document_text", ""))) if record else None,
            "academic_section_count": len(record.get("academic_sections") or []) if record else None,
            "signature_scheme": provenance.get("scheme"),
            "signature_present": bool(provenance.get("signature")),
            "backend_acceptance_via_follow_up": "unknown",
        },
        "citation": {
            "count": len(citations),
            "record_id": citation.get("record_id"),
            "locator": citation.get("locator"),
            "url_matches_document": EXPECTED_DOCUMENT in str(citation.get("url", "")),
            "rendered": "unknown",
        },
        "request": {
            "ui_conversation_submissions": "unknown",
            "prior_session_evidence_supplied": "unknown",
            "approved_scope_sent": "unknown",
        },
        "follow_up": None,
        "preflight": None,
        "artifacts": {"redacted_screenshot": None, "diagnostics": str(EVIDENCE_PATH)},
        "cleanup": {"browser_closed": "unknown", "backend_stopped": "unknown", "frontend_stopped": "unknown"},
        "failure": None,
        "contains_raw_source_or_signature": False,
    }


def sanitized_follow_up(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    acquisition = payload.get("acquisition") if isinstance(payload.get("acquisition"), dict) else {}
    citations = payload.get("citations") if isinstance(payload.get("citations"), list) else []
    citation = citations[0] if citations and isinstance(citations[0], dict) else {}
    return {
        "response_status": payload.get("status"),
        "response_code": payload.get("response_code"),
        "source_scope": payload.get("source_scope"),
        "generation_source": payload.get("generation_source"),
        "generation_fallback_used": payload.get("generation_fallback_used"),
        "acquisition_status": acquisition.get("status"),
        "additional_source_acquisitions": acquisition.get("additional_source_acquisitions"),
        "session_evidence_submitted": acquisition.get("session_evidence_submitted"),
        "session_evidence_accepted": acquisition.get("session_evidence_accepted"),
        "session_evidence_matched": acquisition.get("session_evidence_matched"),
        "session_evidence_reused": acquisition.get("session_evidence_reused"),
        "citation_count": len(citations),
        "citation_record_id": citation.get("record_id"),
        "citation_locator": citation.get("locator"),
        "citation_url_matches_document": EXPECTED_DOCUMENT in str(citation.get("url", "")),
        "citation_rendered": "unknown",
        "submitted_evidence_count": "unknown",
        "submitted_record_id_matches": "unknown",
        "submitted_signed_evidence": "unknown",
    }


def preflight() -> dict[str, Any]:
    """Fail before starting local servers or a source-capable browser."""
    require(CHROME_PATH.is_file(), "Installed Chrome executable was not found")
    require((ROOT / "frontend" / "node_modules" / "vite" / "bin" / "vite.js").is_file(), "Vite dependency is missing")
    manifest = json.loads((ROOT / "data" / "syllabi" / "sample-manifest.json").read_text(encoding="utf-8"))
    matches = [item for item in manifest.get("documents", []) if (
        item.get("course_code"), str(item.get("term_id")), str(item.get("section")), item.get("source_document_id"), item.get("view_url")
    ) == ("CAP4773", "202608", "001", EXPECTED_DOCUMENT, EXPECTED_URL)]
    require(len(matches) == 1, "Exact approved CAP4773 mapping was not found")
    require(not EVIDENCE_PATH.exists() and not SCREENSHOT_PATH.exists(), "Future-attempt artifact path already exists")
    for port in (14173, 18100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", port))
    offline = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_syllabus_collector.py", "tests/test_session_evidence.py", "tests/test_bounded_cap4773_harness.py"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False,
    )
    require(offline.returncode == 0, "Offline acquisition prerequisites failed")
    return {"mapping_verified": True, "ports_idle": True, "offline_tests_passed": True}


def write_diagnostics(diagnostics: dict[str, Any]) -> None:
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(json.dumps(diagnostics, indent=2, sort_keys=True) + "\n", encoding="utf-8")


async def capture_redacted_screenshot(page, diagnostics: dict[str, Any]) -> None:
    if page is None:
        return
    try:
        SCREENSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        masks = [page.locator(".chat-message p"), page.locator(".context-grid"), page.locator("textarea")]
        await page.screenshot(path=str(SCREENSHOT_PATH), full_page=True, mask=masks)
        diagnostics["artifacts"]["redacted_screenshot"] = str(SCREENSHOT_PATH)
    except Exception:
        diagnostics["artifacts"]["redacted_screenshot"] = None


async def wait_http(url: str, processes: list[subprocess.Popen], deadline: float) -> None:
    while time.monotonic() < deadline:
        for process in processes:
            require(process.poll() is None, "A local test process exited before readiness")
        try:
            await asyncio.to_thread(lambda: urllib.request.urlopen(url, timeout=1).close())
            return
        except Exception:
            await asyncio.sleep(0.1)
    raise TimeoutError("Local readiness deadline exceeded")


def stop_tree(process: subprocess.Popen | None) -> bool:
    if process is None or process.poll() is not None:
        return True
    subprocess.run(
        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        return False
    return process.poll() is not None


async def execute() -> dict[str, Any]:
    started = time.monotonic()
    signing_key = secrets.token_urlsafe(48)
    environment = os.environ.copy()
    environment.update({
        "CONVERSATIONAL_PARSER_MODE": "deterministic",
        "RAG_GENERATION_MODE": "fallback",
        "GEMINI_API_KEY": "",
        "SESSION_EVIDENCE_SIGNING_KEY": signing_key,
        "CATALOG_ACQUISITION_ENABLED": "false",
        "SYLLABUS_ACQUISITION_ENABLED": "true",
        "ACQUISITION_BROWSER_MODE": "headed",
        "ACQUISITION_TIMEOUT_SECONDS": "20",
        "ACQUISITION_TEST_CATALOG_BUDGET": "0",
        "ACQUISITION_TEST_SYLLABUS_BUDGET": "1",
        "ACQUISITION_MAX_RENDERED_HTML_BYTES": str(2 * 1024 * 1024),
        "SMARTADVISOR_CORS_ORIGINS": FRONTEND_URL,
        "VITE_API_URL": BACKEND_URL,
    })
    backend: subprocess.Popen | None = None
    frontend: subprocess.Popen | None = None
    browser = None
    playwright = None
    page = None
    diagnostics = sanitized_diagnostics(None)
    diagnostics["failure_stage"] = "startup"
    conversation_requests: list[dict[str, Any]] = []
    preflight_result: dict[str, Any] | None = None
    diagnostics_path_available = not EVIDENCE_PATH.exists()
    failure: BaseException | None = None
    try:
        preflight_result = preflight()
        diagnostics["preflight"] = preflight_result
        backend = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.api:app", "--host", "127.0.0.1", "--port", "18100", "--workers", "1"],
            cwd=ROOT, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        frontend = subprocess.Popen(
            ["node", str(ROOT / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"), "--host", "127.0.0.1", "--port", "14173"],
            cwd=ROOT / "frontend", env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        await wait_http(f"{BACKEND_URL}/", [backend, frontend], started + 20)
        await wait_http(FRONTEND_URL, [backend, frontend], started + 20)

        from playwright.async_api import async_playwright
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=False, executable_path=str(CHROME_PATH))
        context = await browser.new_context()
        page = await context.new_page()

        def observe_request(request) -> None:
            if request.url == f"{BACKEND_URL}/conversation" and request.method == "POST":
                conversation_requests.append(request.post_data_json or {})

        page.on("request", observe_request)
        diagnostics["failure_stage"] = "ui_submission"
        await page.goto(f"{FRONTEND_URL}/chatbot", wait_until="networkidle")
        await page.locator("details.conversation-context-controls summary").click()
        await page.get_by_label("Source term").fill("202608")
        await page.get_by_label("Source section").fill("001")
        await page.get_by_label("Student Question or Planning Query:").fill(
            "What grading information is in the syllabus for CAP 4773?"
        )
        async with page.expect_response(
            lambda response: response.url == f"{BACKEND_URL}/conversation" and response.request.method == "POST",
            timeout=45_000,
        ) as response_info:
            await page.get_by_role("button", name="Send").click()
        response = await response_info.value
        payload = await response.json()
        diagnostics = sanitized_diagnostics(payload)
        diagnostics["preflight"] = preflight_result
        diagnostics["failure_stage"] = "response_validation"
        request_body = conversation_requests[0] if len(conversation_requests) == 1 else {}
        diagnostics["request"] = {
            "ui_conversation_submissions": len(conversation_requests),
            "prior_session_evidence_supplied": bool(request_body.get("session_evidence")),
            "approved_scope_sent": request_body.get("term") == "202608"
            and (request_body.get("session_context") or {}).get("section") == "001",
        }

        evidence = payload.get("acquired_evidence") if isinstance(payload.get("acquired_evidence"), list) else []
        rendered_citation = page.locator('ol[aria-label="Source citations"]').last
        try:
            await rendered_citation.wait_for(state="visible", timeout=5_000)
            diagnostics["citation"]["rendered"] = True
        except Exception:
            diagnostics["citation"]["rendered"] = False

        # Persist available metadata and a redacted UI image before assertions.
        await capture_redacted_screenshot(page, diagnostics)
        if diagnostics_path_available:
            write_diagnostics(diagnostics)

        acquisition = payload.get("acquisition") or {}
        record = evidence[0] if evidence else {}
        source = record.get("source") or {}
        provenance = record.get("session_provenance") or {}
        citations = payload.get("citations") or []
        citation = citations[0] if citations else {}
        require(response.status == 200, "Conversation HTTP status was not successful")
        require(len(conversation_requests) == 1, "Expected exactly one UI conversation submission")
        require(not request_body.get("session_evidence"), "Request unexpectedly supplied prior session evidence")
        require(diagnostics["request"]["approved_scope_sent"], "Request scope did not match approval")
        require(acquisition.get("status") == "acquired", "Final acquisition status was not acquired")
        require(acquisition.get("probe_status") == "anonymous_full_document", "Probe did not report a complete anonymous document")
        require(acquisition.get("additional_source_acquisitions") == 1, "Acquisition count was not one")
        require(acquisition.get("request_count") == 1, "Logical navigation count was not one")
        require(isinstance(acquisition.get("actual_observed_responses"), int) and acquisition["actual_observed_responses"] <= 60, "Observed response budget was unavailable or exceeded")
        require(acquisition.get("cleanup") == "completed", "Acquisition browser cleanup was not completed")
        require(acquisition.get("access_denials") == 0, "An access denial was observed")
        require(acquisition.get("essential_document_failures") == 0, "An essential document failure was observed")
        require(payload.get("status") == "grounded_answer", "Response was not grounded")
        require(payload.get("source_scope") == EXPECTED_SCOPE, "Returned source scope did not match approval")
        require(payload.get("generation_source") != "provider" and not payload.get("model_id"), "Unexpected provider generation was used")
        require(len(evidence) == 1, "Expected one acquired evidence record")
        require(record.get("record_category") == "syllabus", "Evidence category was not syllabus")
        require(record.get("course_code") == "CAP4773", "Evidence course identity mismatch")
        require((record.get("term_scope") or {}).get("term_id") == "202608", "Evidence term identity mismatch")
        require((record.get("section_scope") or {}).get("section") == "001", "Evidence section identity mismatch")
        require(source.get("source_id") == EXPECTED_DOCUMENT, "Evidence document identity mismatch")
        require(len(str(record.get("document_text", ""))) >= 500, "Evidence content was not substantive")
        require(len(record.get("academic_sections") or []) >= 2, "Evidence academic sections were incomplete")
        require(provenance.get("scheme") == "hmac-sha256-v1" and bool(provenance.get("signature")), "Evidence signature was missing")
        require(bool(citations) and citation.get("record_id") == record.get("record_id"), "Citation record identity mismatch")
        require(EXPECTED_DOCUMENT in str(citation.get("url", "")), "Citation document identity mismatch")
        require(diagnostics["citation"]["rendered"] is True, "Citation was not rendered in the UI")

        diagnostics["failure_stage"] = "follow_up_submission"
        await page.get_by_label("Student Question or Planning Query:").fill(
            "Which letter grade ranges are listed in that same syllabus grading scale?"
        )
        async with page.expect_response(
            lambda follow_response: follow_response.url == f"{BACKEND_URL}/conversation" and follow_response.request.method == "POST",
            timeout=45_000,
        ) as follow_response_info:
            await page.get_by_role("button", name="Send").click()
        follow_response = await follow_response_info.value
        follow_payload = await follow_response.json()
        follow_diagnostics = sanitized_follow_up(follow_payload)
        diagnostics["follow_up"] = follow_diagnostics
        diagnostics["failure_stage"] = "follow_up_validation"

        follow_request = conversation_requests[1] if len(conversation_requests) == 2 else {}
        submitted_evidence = follow_request.get("session_evidence") if isinstance(follow_request.get("session_evidence"), list) else []
        submitted_record = submitted_evidence[0] if submitted_evidence and isinstance(submitted_evidence[0], dict) else {}
        submitted_provenance = submitted_record.get("session_provenance") if isinstance(submitted_record.get("session_provenance"), dict) else {}
        follow_diagnostics["submitted_evidence_count"] = len(submitted_evidence)
        follow_diagnostics["submitted_record_id_matches"] = submitted_record.get("record_id") == record.get("record_id")
        follow_diagnostics["submitted_signed_evidence"] = (
            submitted_provenance.get("scheme") == "hmac-sha256-v1" and bool(submitted_provenance.get("signature"))
        )
        follow_acquisition = follow_payload.get("acquisition") if isinstance(follow_payload.get("acquisition"), dict) else {}
        follow_citations = follow_payload.get("citations") if isinstance(follow_payload.get("citations"), list) else []
        follow_citation = follow_citations[0] if follow_citations else {}
        budget = acquisition.get("test_budget") if isinstance(acquisition.get("test_budget"), dict) else {}
        follow_diagnostics["acquisition_budget_remaining_after_first"] = (
            budget.get("limit") - budget.get("used")
            if isinstance(budget.get("limit"), int) and isinstance(budget.get("used"), int)
            else "unknown"
        )
        try:
            await page.locator('ol[aria-label="Source citations"]').last.wait_for(state="visible", timeout=5_000)
            follow_diagnostics["citation_rendered"] = True
        except Exception:
            follow_diagnostics["citation_rendered"] = False
        backend_accepted_reuse = (
            follow_acquisition.get("session_evidence_submitted") == 1
            and follow_acquisition.get("session_evidence_accepted") == 1
            and follow_acquisition.get("session_evidence_matched") == 1
            and follow_acquisition.get("session_evidence_reused") is True
        )
        diagnostics["evidence"]["backend_acceptance_via_follow_up"] = backend_accepted_reuse

        # Persist the complete two-turn metadata and redacted UI before assertions.
        await capture_redacted_screenshot(page, diagnostics)
        if diagnostics_path_available:
            write_diagnostics(diagnostics)

        require(follow_response.status == 200, "Follow-up conversation HTTP status was not successful")
        require(len(conversation_requests) == 2, "Expected exactly two UI conversation submissions")
        require(len(submitted_evidence) == 1, "Frontend did not retain and submit one evidence record")
        require(follow_diagnostics["submitted_record_id_matches"] is True, "Frontend submitted the wrong evidence record")
        require(follow_diagnostics["submitted_signed_evidence"] is True, "Frontend did not retain signed evidence")
        require(follow_diagnostics["acquisition_budget_remaining_after_first"] == 0, "Follow-up acquisition budget was not exhausted before follow-up")
        require(backend_accepted_reuse, "Backend did not accept and match the submitted evidence")
        require(follow_acquisition.get("status") == "not_needed", "Follow-up did not reuse retained evidence")
        require(follow_acquisition.get("additional_source_acquisitions") == 0, "Follow-up attempted another source acquisition")
        require(follow_payload.get("status") == "grounded_answer", "Follow-up was not source grounded")
        require(follow_payload.get("response_code") == "SESSION_EVIDENCE_ANSWER", "Follow-up evidence was insufficient")
        require(follow_payload.get("source_scope") == EXPECTED_SCOPE, "Follow-up source scope did not match")
        require(follow_payload.get("generation_source") != "provider" and not follow_payload.get("model_id"), "Follow-up unexpectedly used provider generation")
        require(bool(follow_citations) and follow_citation.get("record_id") == record.get("record_id"), "Follow-up citation record identity mismatch")
        require(EXPECTED_DOCUMENT in str(follow_citation.get("url", "")), "Follow-up citation document identity mismatch")
        require(follow_diagnostics["citation_rendered"] is True, "Follow-up citation was not rendered in the UI")
        diagnostics["conclusion"] = "passed"
        diagnostics["failure_stage"] = None
    except BaseException as exc:
        failure = exc
        diagnostics["conclusion"] = "failed"
        diagnostics["failure"] = {"error_type": type(exc).__name__, "stage": diagnostics.get("failure_stage")}
        if page is not None and diagnostics["artifacts"].get("redacted_screenshot") is None:
            await capture_redacted_screenshot(page, diagnostics)
    finally:
        if browser is not None:
            try:
                await browser.close()
                diagnostics["cleanup"]["browser_closed"] = True
            except Exception:
                diagnostics["cleanup"]["browser_closed"] = False
        if playwright is not None:
            try:
                await playwright.stop()
            except Exception:
                diagnostics["cleanup"]["browser_closed"] = False
        diagnostics["cleanup"]["frontend_stopped"] = stop_tree(frontend)
        diagnostics["cleanup"]["backend_stopped"] = stop_tree(backend)
        diagnostics["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        if diagnostics_path_available:
            write_diagnostics(diagnostics)
    if failure is not None:
        raise failure
    return diagnostics


async def bounded() -> dict[str, Any]:
    return await asyncio.wait_for(execute(), timeout=90.0)


if __name__ == "__main__":
    print(json.dumps(asyncio.run(bounded()), sort_keys=True))
