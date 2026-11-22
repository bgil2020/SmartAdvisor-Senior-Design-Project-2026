"""Representative saved-evidence replay against real Vite and FastAPI servers.

The live-acquired syllabus body was not retained. This uses the regression
fixture with the approved localized source identity and exercises real record
validation, signing, browser retention, retrieval, citations, reset, and stale
response protection. Test budgets are zero, so no external request can start.
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND_URL = "http://127.0.0.1:18100"
FRONTEND_URL = "http://127.0.0.1:14173"
ARTIFACT_DIR = ROOT / "docs" / "ui-verification"


def wait_http(url: str, processes: list[subprocess.Popen], timeout: float = 45) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for process in processes:
            if process.poll() is not None:
                raise RuntimeError(f"Local verification server exited with code {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status < 500:
                    return
        except Exception:
            time.sleep(0.2)
    raise TimeoutError(f"Timed out waiting for {url}")


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


async def verify(saved_record: dict) -> dict:
    from playwright.async_api import async_playwright

    browser_path = next((path for path in (
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ) if path.exists()), None)
    if browser_path is None:
        raise RuntimeError("No installed Chrome or Edge executable is available")

    request_log: list[dict] = []
    response_log: list[dict] = []
    catalog_responses: list[int] = []
    fixture_supplied = False
    stale_started = asyncio.Event()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, executable_path=str(browser_path))
        page = await browser.new_page(viewport={"width": 1440, "height": 1200})
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        page.on(
            "response",
            lambda response: catalog_responses.append(response.status)
            if response.url.rstrip("/").endswith("/courses")
            else None,
        )

        async def conversation_route(route, request):
            nonlocal fixture_supplied
            body = json.loads(request.post_data or "{}")
            message = str(body.get("message", ""))
            fixture_request = not fixture_supplied and "grading section" in message.casefold()
            if fixture_request:
                body["session_evidence"] = [saved_record]
                body["session_context"] = {"course_code": "COP4331", "term_id": "202608", "section": "002"}
            request_log.append({
                "message": message,
                "evidence_count": len(body.get("session_evidence") or []),
                "scope": body.get("session_context"),
                "sections": body.get("sections"),
                "selected_sections": body.get("selected_sections"),
            })
            if "stale pending" in message.casefold():
                stale_started.set()
                await asyncio.sleep(1.25)
            upstream = await route.fetch(post_data=json.dumps(body))
            payload = await upstream.json()
            print(json.dumps({
                "browser_replay_step": message,
                "backend_status": payload.get("status"),
                "response_code": payload.get("response_code"),
                "acquisition_status": (payload.get("acquisition") or {}).get("status"),
            }), flush=True)
            if fixture_request:
                payload["acquired_evidence"] = [saved_record]
                payload["acquisition"] = {"status": "representative_fixture_supplied", "additional_source_acquisitions": 0}
                fixture_supplied = True
                await route.fulfill(response=upstream, json=payload)
            else:
                await route.fulfill(response=upstream)
            response_log.append({
                "message": message,
                "status": payload.get("status"),
                "response_code": payload.get("response_code"),
                "additional_source_acquisitions": (payload.get("acquisition") or {}).get("additional_source_acquisitions"),
                "acquisition_status": (payload.get("acquisition") or {}).get("status"),
                "session_evidence_submitted": (payload.get("acquisition") or {}).get("session_evidence_submitted"),
                "session_evidence_accepted": (payload.get("acquisition") or {}).get("session_evidence_accepted"),
                "session_evidence_matched": (payload.get("acquisition") or {}).get("session_evidence_matched"),
                "session_evidence_reused": (payload.get("acquisition") or {}).get("session_evidence_reused"),
                "scope": payload.get("source_scope"),
                "citation_count": len(payload.get("citations") or []),
                "citation_locators": [item.get("locator") for item in payload.get("citations") or []],
                "engine_executed": payload.get("engine_executed"),
            })

        await page.route(f"{BACKEND_URL}/conversation", conversation_route)
        await page.goto(FRONTEND_URL, wait_until="networkidle")
        welcome_rendered = await page.get_by_role("heading", name="Welcome to SmartAdvisor").is_visible()
        await page.screenshot(path=ARTIFACT_DIR / "home.png", full_page=True)

        await page.get_by_role("button", name="Open SmartAdvisor Chat").click()
        chat_path = page.url.endswith("/chatbot")
        await page.reload(wait_until="networkidle")
        chat_refresh_rendered = await page.get_by_role("heading", name="SmartAdvisor Chat").is_visible()
        await page.get_by_role("button", name="Home", exact=True).click()

        await page.get_by_role("button", name="Go to Forms & Engines").click()
        await page.locator("#course-select-dropdown:not([disabled])").wait_for()
        forms_path = page.url.endswith("/forms")
        await page.reload(wait_until="networkidle")
        await page.locator("#course-select-dropdown:not([disabled])").wait_for()
        forms_refresh_rendered = await page.get_by_role(
            "heading", name="Real Course Catalog & Section Search"
        ).is_visible()
        catalog_option_count = await page.locator("#course-select-dropdown option").count()
        forms_rendered = all((
            await page.get_by_role("heading", name="Real Course Catalog & Section Search").is_visible(),
            await page.get_by_role("heading", name="Proposed Schedule").is_visible(),
            await page.get_by_role("heading", name="3. Course Compatibility & Workload Screener").count() == 1,
            await page.get_by_role("heading", name="Online Course Override Evaluator").count() == 1,
        ))

        await page.locator("#quick-select-CAP-4773").click()
        cap_section = page.locator(".section-option").filter(has_text="Sec 002")
        await cap_section.get_by_role("button", name="+ Add", exact=True).click()
        await page.locator("#quick-select-MAP-3305").click()
        map_section = page.locator(".section-option").filter(has_text="Sec 001")
        await map_section.get_by_role("button", name="+ Add", exact=True).click()
        selected_count = await page.locator(".selected-section-card").count()
        calendar_event_count = await page.locator(".calendar-event").count()
        await page.locator(".selected-section-card").filter(has_text="MAP 3305").get_by_role("button", name="Remove").click()
        remove_updated_calendar = await page.locator(".selected-section-card").count() == 1
        await map_section.get_by_role("button", name="+ Add", exact=True).click()
        readd_restored_selection = await page.locator(".selected-section-card").count() == 2
        await page.locator(".planning-workspace").first.screenshot(path=ARTIFACT_DIR / "forms-shared-workspace.png")

        await page.get_by_placeholder("e.g., COP4331, MAP3305, CDA4630").fill(
            "COP4331, MAP3305, CDA4630, CEN4214"
        )
        await page.get_by_role("button", name="Evaluate Course Compatibility").click()
        compatibility_card = page.locator("#compatibility-response-card")
        await compatibility_card.wait_for()
        compatibility_result_rendered = await compatibility_card.get_by_text(
            "Compatibility Result for Evie Woods", exact=False
        ).is_visible()
        await compatibility_card.screenshot(path=ARTIFACT_DIR / "form-result.png")
        await page.get_by_role("button", name="AI Assistant Chat").click()
        chat_rendered = await page.get_by_role("heading", name="SmartAdvisor Chat").is_visible()
        shared_selection_visible = await page.get_by_text("CAP 4773 sec 002", exact=False).first.is_visible() and await page.get_by_text("MAP 3305 sec 001", exact=False).first.is_visible()
        left_box = await page.locator(".chat-schedule-panel").bounding_box()
        right_box = await page.locator(".chat-conversation-panel").bounding_box()
        desktop_ratio = left_box["width"] / (left_box["width"] + right_box["width"])
        desktop_split_valid = 0.60 <= desktop_ratio <= 0.70
        await page.locator(".chat-workspace").screenshot(path=ARTIFACT_DIR / "chatbot-workspace-desktop.png")

        question = page.locator("#conversational-message-input")
        await question.fill("Do these classes conflict?")
        await page.get_by_role("button", name="Send", exact=True).click()
        await page.get_by_text("SCHEDULE_CONFLICT_FOUND", exact=False).wait_for()
        selected_context_result = await page.get_by_text("Selected schedule sent:", exact=False).is_visible()
        await page.locator(".calendar-event").first.scroll_into_view_if_needed()
        await page.screenshot(path=ARTIFACT_DIR / "selected-calendar-backend-chat.png")

        await page.locator(".conversation-context-controls summary").click()
        await page.get_by_label("Source term").fill("202608")
        await page.get_by_label("Source section").fill("002")

        await question.fill("What does the grading section say for COP 4331?")
        await page.get_by_role("button", name="Send", exact=True).click()
        await page.get_by_text("Source-Grounded Session Answer").wait_for()
        await page.get_by_role("list", name="Source citations").wait_for()
        await page.locator("#conversational-response-card").screenshot(
            path=ARTIFACT_DIR / "chatbot-result.png"
        )

        await question.fill("What are the learning outcomes for that class?")
        await page.get_by_role("button", name="Send", exact=True).click()
        await page.get_by_text("Learning Outcomes:").wait_for()
        multiple_exchanges_visible = await page.locator(".chat-message").count() >= 6

        await page.set_viewport_size({"width": 760, "height": 1000})
        narrow_left = await page.locator(".chat-schedule-panel").bounding_box()
        narrow_right = await page.locator(".chat-conversation-panel").bounding_box()
        narrow_stacked = narrow_right["y"] > narrow_left["y"] + narrow_left["height"] - 5
        await page.screenshot(path=ARTIFACT_DIR / "chatbot-workspace-narrow.png", full_page=True)
        await page.set_viewport_size({"width": 1440, "height": 1200})

        await question.fill("What does that class syllabus say about the cafeteria menu?")
        await page.get_by_role("button", name="Send", exact=True).click()
        await page.get_by_text("did not refetch it").wait_for()

        await question.fill("What grading details are in that class syllabus for stale pending verification?")
        await page.get_by_role("button", name="Send", exact=True).click()
        await asyncio.wait_for(stale_started.wait(), timeout=3)
        requests_before_clear = len(request_log)
        await page.get_by_role("button", name="Clear chat").click()
        await asyncio.sleep(1.5)
        reset_ignored_stale = await page.locator("#conversational-response-card").count() == 0
        clear_preserved_selection = await page.locator(".selected-section-card").count() == 2
        clear_made_no_request = len(request_log) == requests_before_clear
        reset_cleared_scope = (
            await page.get_by_label("Source term").input_value() == ""
            and await page.get_by_label("Source section").input_value() == ""
        )

        await page.get_by_label("Source term").fill("202608")
        await page.get_by_label("Source section").fill("002")
        await question.fill("What does the grading section say for COP 4331?")
        await page.get_by_role("button", name="Send", exact=True).click()
        await page.get_by_text("Source Unavailable").wait_for()

        await page.get_by_role("button", name="Home", exact=True).click()
        returned_home = (
            page.url.rstrip("/") == FRONTEND_URL
            and await page.get_by_role("heading", name="Welcome to SmartAdvisor").is_visible()
        )

        await browser.close()

    follow_up = next(item for item in response_log if item["message"].startswith("What are the learning outcomes"))
    fallback = next(item for item in response_log if "cafeteria" in item["message"])
    schedule_response = next(item for item in response_log if item["message"] == "Do these classes conflict?")
    schedule_request = next(item for item in request_log if item["message"] == "Do these classes conflict?")
    initial_answer = next(item for item in response_log if item["message"].startswith("What does the grading section"))
    post_reset = response_log[-1]
    passed = all((
        initial_answer["status"] == "grounded_answer",
        initial_answer["citation_count"] > 0,
        schedule_response["status"] == "engine_executed",
        schedule_response["engine_executed"],
        [item["crn"] for item in schedule_request["sections"]] == ["19416", "16644"],
        schedule_request["selected_sections"] == schedule_request["sections"],
        welcome_rendered,
        forms_rendered,
        forms_path,
        forms_refresh_rendered,
        compatibility_result_rendered,
        chat_rendered,
        chat_path,
        chat_refresh_rendered,
        shared_selection_visible,
        selected_count == 2,
        calendar_event_count > 0,
        remove_updated_calendar,
        readd_restored_selection,
        desktop_split_valid,
        selected_context_result,
        multiple_exchanges_visible,
        narrow_stacked,
        clear_preserved_selection,
        clear_made_no_request,
        returned_home,
        catalog_option_count > 1,
        bool(catalog_responses) and all(status == 200 for status in catalog_responses),
        follow_up["status"] == "grounded_answer",
        follow_up["additional_source_acquisitions"] == 0,
        follow_up["acquisition_status"] == "not_needed",
        follow_up["session_evidence_submitted"] == 1,
        follow_up["session_evidence_accepted"] == 1,
        follow_up["session_evidence_matched"] == 1,
        follow_up["session_evidence_reused"] is True,
        follow_up["scope"] == {"course_code": "COP4331", "term_id": "202608", "section": "002"},
        any("learning" in str(locator).casefold() for locator in follow_up["citation_locators"]),
        fallback["response_code"] == "SESSION_EVIDENCE_INSUFFICIENT",
        fallback["additional_source_acquisitions"] == 0,
        fallback["acquisition_status"] == "not_needed",
        reset_ignored_stale,
        reset_cleared_scope,
        post_reset["status"] == "acquisition_failed",
        post_reset["acquisition_status"] == "acquisition_budget_exhausted",
        post_reset["additional_source_acquisitions"] == 0,
        any("grading" in str(locator).casefold() for locator in initial_answer["citation_locators"]),
    ))
    return {
        "status": "passed" if passed else "failed",
        "verification_kind": "representative_fixture_localized_source_replay",
        "integrated_ui": {
            "welcome_rendered": welcome_rendered,
            "forms_and_engines_rendered": forms_rendered,
            "forms_path": forms_path,
            "forms_refresh_rendered": forms_refresh_rendered,
            "compatibility_result_rendered": compatibility_result_rendered,
            "chat_rendered": chat_rendered,
            "chat_path": chat_path,
            "chat_refresh_rendered": chat_refresh_rendered,
            "desktop_workspace_ratio": desktop_ratio,
            "desktop_split_valid": desktop_split_valid,
            "narrow_stacked": narrow_stacked,
            "selected_count": selected_count,
            "calendar_event_count": calendar_event_count,
            "remove_updated_calendar": remove_updated_calendar,
            "readd_restored_selection": readd_restored_selection,
            "shared_selection_visible": shared_selection_visible,
            "multiple_exchanges_visible": multiple_exchanges_visible,
            "clear_preserved_selection": clear_preserved_selection,
            "clear_made_no_request": clear_made_no_request,
            "returned_home": returned_home,
            "catalog_option_count": catalog_option_count,
            "catalog_http_statuses": catalog_responses,
        },
        "screenshots": [
            str(ARTIFACT_DIR / "home.png"),
            str(ARTIFACT_DIR / "forms-shared-workspace.png"),
            str(ARTIFACT_DIR / "form-result.png"),
            str(ARTIFACT_DIR / "chatbot-workspace-desktop.png"),
            str(ARTIFACT_DIR / "selected-calendar-backend-chat.png"),
            str(ARTIFACT_DIR / "chatbot-workspace-narrow.png"),
            str(ARTIFACT_DIR / "chatbot-result.png"),
        ],
        "schedule_request": schedule_request,
        "schedule_response": schedule_response,
        "initial_answer": initial_answer,
        "follow_up": follow_up,
        "fallback": fallback,
        "reset_ignored_stale": reset_ignored_stale,
        "reset_cleared_scope": reset_cleared_scope,
        "post_reset_missing_evidence": post_reset,
        "request_evidence_counts": [item["evidence_count"] for item in request_log],
    }


def main() -> int:
    signing_key = secrets.token_urlsafe(48)
    environment = os.environ.copy()
    environment.update({
        "CONVERSATIONAL_PARSER_MODE": "deterministic",
        "RAG_GENERATION_MODE": "fallback",
        "SESSION_EVIDENCE_SIGNING_KEY": signing_key,
        "GEMINI_API_KEY": "",
        "CATALOG_ACQUISITION_ENABLED": "true",
        "SYLLABUS_ACQUISITION_ENABLED": "true",
        "ACQUISITION_BROWSER_MODE": "headed",
        "ACQUISITION_TEST_CATALOG_BUDGET": "0",
        "ACQUISITION_TEST_SYLLABUS_BUDGET": "0",
        "SMARTADVISOR_CORS_ORIGINS": FRONTEND_URL,
        "VITE_API_URL": BACKEND_URL,
    })
    os.environ.update(environment)
    from backend.course_descriptions.models import utc_now
    from backend.session_evidence import attach_provenance
    from backend.syllabi.parser import parse_rendered_syllabus

    fixture = ROOT / "tests" / "syllabi" / "fixtures" / "rendered_complete.html"
    record = parse_rendered_syllabus(
        fixture.read_text(encoding="utf-8"), course_code="COP4331", term_id="202608",
        term_name="Fall 2026 1 Full Term", section="002", source_document_id="sb4d8l8wb",
        source_url="https://fau.simplesyllabus.com/en-US/doc/sb4d8l8wb/Fall-2026-1-Full-Term-COP-4331-002-Object-Oriented-Design-%26-Prog?mode=view",
        fetched_at=utc_now(), raw_evidence_ref="session-memory:local-ui-verification",
    )
    saved_record = attach_provenance(record)
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.api:app", "--host", "127.0.0.1", "--port", "18100", "--workers", "1"],
        cwd=ROOT, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    frontend = subprocess.Popen(
        ["node", str(ROOT / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"), "--host", "127.0.0.1", "--port", "14173"],
        cwd=ROOT / "frontend", env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        wait_http(f"{BACKEND_URL}/health", [backend, frontend])
        wait_http(FRONTEND_URL, [backend, frontend])
        result = asyncio.run(verify(saved_record))
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "passed" else 1
    finally:
        stop_process(frontend)
        stop_process(backend)


if __name__ == "__main__":
    raise SystemExit(main())
