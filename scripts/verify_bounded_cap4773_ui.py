"""One separately approved CAP4773 acquisition and Gemini grading diagnostic.

Diagnostics exclude source/answer text, prompts, signatures, credentials, and
private data. Running this file requires a new explicit live-source approval.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from backend.rag.grade_relationships import (
    GRADE_LABEL,
    NUMBER_TOKEN,
    extract_grade_relationships,
    normalize_number,
    validate_grade_relationships,
)
FRONTEND_URL = "http://127.0.0.1:14173"
BACKEND_URL = "http://127.0.0.1:18100"
MODEL = "gemini-3.5-flash-lite"
EXPECTED_SCOPE = {"course_code": "CAP4773", "term_id": "202608", "section": "001"}
EXPECTED_DOCUMENT = "fjhz2vvga"
EXPECTED_URL = "https://fau.simplesyllabus.com/doc/fjhz2vvga/Fall-2026-1-Full-Term-CAP-4773-001-Intro-Data-Science-Analytics?mode=view"
CHROME_PATH = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
EVIDENCE_PATH = ROOT / "docs" / "acquisition-evidence" / "cap4773-live-grade-relationship-diagnostic-next.json"
SCREENSHOT_PATH = ROOT / "docs" / "acquisition-evidence" / "cap4773-live-grade-relationship-diagnostic-next-redacted.png"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def current_code_state() -> dict[str, Any]:
    """Return commit and tracked-diff state without inspecting file contents."""
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True,
    ).stdout.strip()
    tracked = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT, text=True, capture_output=True, check=True,
    ).stdout.strip()
    return {"tested_head": head, "tracked_changes_present": bool(tracked)}


def sanitized_diagnostics(
    payload: dict[str, Any] | None,
    *,
    code_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return bounded metadata without retaining raw source or secret values."""
    payload = payload or {}
    acquisition = payload.get("acquisition") if isinstance(payload.get("acquisition"), dict) else {}
    evidence = payload.get("acquired_evidence") if isinstance(payload.get("acquired_evidence"), list) else []
    citations = payload.get("citations") if isinstance(payload.get("citations"), list) else []
    record = evidence[0] if evidence and isinstance(evidence[0], dict) else {}
    source = record.get("source") if isinstance(record.get("source"), dict) else {}
    provenance = record.get("session_provenance") if isinstance(record.get("session_provenance"), dict) else {}
    citation = citations[0] if citations and isinstance(citations[0], dict) else {}
    state = code_state or current_code_state()
    return {
        "schema_version": "1.0",
        "attempt_label": "future-single-turn-grade-relationship-diagnostic-requires-separate-approval",
        "conclusion": "in_progress",
        "tested_head": state["tested_head"],
        "combined_harness_uncommitted": state["tracked_changes_present"],
        "response": {
            "status": payload.get("status"),
            "response_code": payload.get("response_code"),
            "source_scope": payload.get("source_scope"),
            "generation_source": payload.get("generation_source"),
            "generation_fallback_used": payload.get("generation_fallback_used"),
            "model_id": payload.get("model_id"),
            "answer_support_check": "unknown",
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
        "provider": {
            "model": MODEL,
            "request_budget": 1,
            "accepted_provider_answers": 0,
            "automatic_retries": 0,
        },
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
        "model_id": payload.get("model_id"),
        "answer_support_check": "unknown",
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


def _without_nonclaim_identifiers(text: str, record: dict[str, Any]) -> str:
    """Remove citations and scoped identifiers before academic-number comparison."""
    cleaned = re.sub(r"\[[^\]]+\]", " ", text)
    course_code = re.sub(r"[^A-Za-z0-9]", "", str(record.get("course_code", "")))
    match = re.fullmatch(r"([A-Za-z]+)(\d+)", course_code)
    if match:
        letters, digits = match.groups()
        cleaned = re.sub(
            rf"(?<![A-Za-z0-9]){re.escape(letters)}\s*[- ]?\s*{re.escape(digits)}(?![A-Za-z0-9])",
            " ", cleaned, flags=re.IGNORECASE,
        )
    term_id = str((record.get("term_scope") or {}).get("term_id", ""))
    section = str((record.get("section_scope") or {}).get("section", ""))
    if term_id:
        cleaned = re.sub(rf"\bterm\s*{re.escape(term_id)}\b", " ", cleaned, flags=re.IGNORECASE)
    if section:
        cleaned = re.sub(rf"\bsection\s*0*{re.escape(section.lstrip('0') or '0')}\b", " ", cleaned, flags=re.IGNORECASE)
    return cleaned


def _category_percentages(text: str) -> set[tuple[str, str]]:
    pattern = re.compile(
        rf"(?<![A-Za-z0-9])(?P<label>[A-Za-z][A-Za-z0-9 &/()-]{{0,48}}?)"
        rf"\s*(?:is|are|:|=)\s*(?P<number>{NUMBER_TOKEN})\s*%?",
        re.IGNORECASE,
    )
    relationships = set()
    for match in pattern.finditer(text):
        label = re.sub(r"\s+", " ", match.group("label")).strip(" -():")
        if re.fullmatch(GRADE_LABEL, label, flags=re.IGNORECASE):
            continue
        relationships.add((label.casefold(), normalize_number(match.group("number"))))
    return relationships


def support_check(payload: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """Check numeric values and their grade/category bindings in cited evidence only."""
    citations = payload.get("citations") if isinstance(payload.get("citations"), list) else []
    sections = record.get("academic_sections") if isinstance(record.get("academic_sections"), list) else []
    by_locator = {
        str(section.get("locator")): str(section.get("text", ""))
        for section in sections
        if isinstance(section, dict)
    }
    cited_texts = [by_locator.get(str(item.get("locator"))) for item in citations if isinstance(item, dict)]
    locators_resolved = bool(citations) and all(text is not None for text in cited_texts)
    source_text = " ".join(text or "" for text in cited_texts)
    answer = str(payload.get("response_text", ""))
    answer_claim_text = _without_nonclaim_identifiers(answer, record)
    answer_numbers = {normalize_number(value) for value in re.findall(NUMBER_TOKEN, answer_claim_text)}
    source_numbers = {normalize_number(value) for value in re.findall(NUMBER_TOKEN, source_text)}
    numeric_claims_supported = answer_numbers.issubset(source_numbers)
    grade_validation = validate_grade_relationships(answer_claim_text, [source_text])
    grade_comparison = grade_validation["comparison"]
    unsupported_grade_relationships = [
        item["answer_relationship"] for item in grade_comparison if item["status"] == "mismatch"
    ]
    unverified_grade_relationships = [
        item["answer_relationship"] for item in grade_comparison if item["status"] == "unknown"
    ]
    answer_categories = _category_percentages(answer_claim_text)
    source_categories = _category_percentages(source_text)
    unsupported_categories = sorted(answer_categories - source_categories)
    citation_ids = {
        str(item.get("source_id"))
        for item in citations
        if isinstance(item, dict) and item.get("source_id")
    }
    citations_inline = bool(citation_ids) and all(f"[{source_id}]" in answer for source_id in citation_ids)
    return {
        "passed": (
            locators_resolved
            and numeric_claims_supported
            and grade_validation["verdict"] in {"verified", "not_applicable"}
            and not unsupported_grade_relationships
            and not unverified_grade_relationships
            and not unsupported_categories
            and citations_inline
        ),
        "cited_locators_resolved": locators_resolved,
        "numeric_claim_count": len(answer_numbers),
        "numeric_claims_supported": numeric_claims_supported,
        "unsupported_numeric_values": sorted(answer_numbers - source_numbers)[:12],
        "grade_range_claim_count": grade_validation["answer_relationship_count"],
        "answer_grade_relationship_count": grade_validation["answer_relationship_count"],
        "source_grade_relationship_count": grade_validation["source_relationship_count"],
        "source_relationship_extraction": grade_validation["source_extraction"],
        "grade_relationship_verdict": grade_validation["verdict"],
        "grade_relationship_comparison": grade_comparison,
        "unsupported_grade_ranges": [
            item for item in unsupported_grade_relationships[:12]
        ],
        "unverified_grade_relationships": unverified_grade_relationships[:12],
        "category_percentage_claim_count": len(answer_categories),
        "unsupported_category_percentages": [
            {"category": label, "percentage": percentage}
            for label, percentage in unsupported_categories[:12]
        ],
        "citation_ids_inline": citations_inline,
    }


def preflight(*, require_provider_key: bool = False) -> dict[str, Any]:
    """Fail before starting local servers or a source-capable browser."""
    require(CHROME_PATH.is_file(), "Installed Chrome executable was not found")
    require((ROOT / "frontend" / "node_modules" / "vite" / "bin" / "vite.js").is_file(), "Vite dependency is missing")
    manifest = json.loads((ROOT / "data" / "syllabi" / "sample-manifest.json").read_text(encoding="utf-8"))
    matches = [item for item in manifest.get("documents", []) if (
        item.get("course_code"), str(item.get("term_id")), str(item.get("section")), item.get("source_document_id"), item.get("view_url")
    ) == ("CAP4773", "202608", "001", EXPECTED_DOCUMENT, EXPECTED_URL)]
    require(len(matches) == 1, "Exact approved CAP4773 mapping was not found")
    require(not EVIDENCE_PATH.exists() and not SCREENSHOT_PATH.exists(), "Future-attempt artifact path already exists")
    generation_code = (ROOT / "backend" / "rag" / "generation.py").read_text(encoding="utf-8")
    require("retry_options=types.HttpRetryOptions(attempts=1)" in generation_code, "Provider retry bound changed")
    key_matches_account_evidence: bool | str = "not_checked_offline"
    if require_provider_key:
        provider_key = os.getenv("GEMINI_API_KEY", "").strip()
        require(bool(provider_key), "GEMINI_API_KEY is not present in the effective environment")
        require(provider_key.endswith("MXzQ"), "Configured Gemini key does not match the approved account evidence")
        key_matches_account_evidence = True
    for port in (14173, 18100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", port))
    offline = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_syllabus_collector.py", "tests/test_session_evidence.py", "tests/test_bounded_cap4773_harness.py"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False,
    )
    require(offline.returncode == 0, "Offline acquisition prerequisites failed")
    return {
        "mapping_verified": True,
        "ports_idle": True,
        "offline_tests_passed": True,
        "provider_retries": 0,
        "configured_key_matches_account_evidence": key_matches_account_evidence,
    }


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
        "RAG_GENERATION_MODE": "gemini",
        "GEMINI_MODEL": MODEL,
        "GEMINI_TIMEOUT_SECONDS": "10",
        "GEMINI_MAX_OUTPUT_TOKENS": "512",
        "GEMINI_TEST_REQUEST_BUDGET": "1",
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
        preflight_result = preflight(require_provider_key=True)
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
        await page.goto(FRONTEND_URL, wait_until="networkidle")
        await page.get_by_role("button", name="Open SmartAdvisor Chat").click()
        require(page.url.endswith("/chatbot"), "Home did not navigate to /chatbot")
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
        first_support = support_check(payload, record)
        diagnostics["response"]["answer_support_check"] = first_support
        diagnostics["provider"]["accepted_provider_answers"] = int(
            payload.get("generation_source") == "provider"
            and payload.get("generation_fallback_used") is False
            and payload.get("model_id") == MODEL
        )
        if diagnostics_path_available:
            write_diagnostics(diagnostics)
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
        require(payload.get("generation_source") == "provider", "First answer was not accepted provider generation")
        require(payload.get("generation_fallback_used") is False, "First answer used fallback generation")
        require(payload.get("model_id") == MODEL, "First answer used the wrong generation model")
        require(first_support["passed"] is True, "First answer was not supported by its cited acquired evidence")
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

        diagnostics["conclusion"] = "passed"
        diagnostics["failure_stage"] = None
        return diagnostics
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--approved-live-grade-diagnostic", action="store_true")
    args = parser.parse_args()
    require(
        args.approved_live_grade_diagnostic,
        "Live grade diagnostic requires explicit approval and --approved-live-grade-diagnostic",
    )
    print(json.dumps(asyncio.run(bounded()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
