"""Saved-evidence browser verification against real Vite and FastAPI servers.

The initial acquisition result is mocked from the existing validated fixture.
No external source URL is requested.
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
    first_response = True
    stale_started = asyncio.Event()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, executable_path=str(browser_path))
        page = await browser.new_page(viewport={"width": 1440, "height": 1200})

        async def conversation_route(route, request):
            nonlocal first_response
            body = json.loads(request.post_data or "{}")
            message = str(body.get("message", ""))
            if first_response:
                body["session_evidence"] = [saved_record]
                body["session_context"] = {"course_code": "COP4331", "term_id": "202608", "section": "002"}
            request_log.append({
                "message": message,
                "evidence_count": len(body.get("session_evidence") or []),
                "scope": body.get("session_context"),
            })
            if "stale pending" in message.casefold():
                stale_started.set()
                await asyncio.sleep(1.25)
            upstream = await route.fetch(post_data=json.dumps(body))
            payload = await upstream.json()
            if first_response:
                payload["acquired_evidence"] = [saved_record]
                payload["acquisition"] = {"status": "mocked_saved_evidence", "additional_source_acquisitions": 1}
                first_response = False
                await route.fulfill(response=upstream, json=payload)
            else:
                await route.fulfill(response=upstream)
            response_log.append({
                "message": message,
                "status": payload.get("status"),
                "response_code": payload.get("response_code"),
                "additional_source_acquisitions": (payload.get("acquisition") or {}).get("additional_source_acquisitions"),
                "scope": payload.get("source_scope"),
                "citation_count": len(payload.get("citations") or []),
            })

        await page.route(f"{BACKEND_URL}/conversation", conversation_route)
        await page.goto(FRONTEND_URL, wait_until="networkidle")
        await page.get_by_label("Source term").fill("202608")
        await page.get_by_label("Source section").fill("002")
        question = page.get_by_label("Student Question or Planning Query:")

        await question.fill("What does the grading section say for COP 4331?")
        await page.get_by_role("button", name="Ask Assistant").click()
        await page.get_by_text("Source-Grounded Session Answer").wait_for()
        await page.get_by_role("list", name="Source citations").wait_for()

        await question.fill("What are the learning outcomes for that class?")
        await page.get_by_role("button", name="Ask Assistant").click()
        await page.get_by_text("Learning Outcomes:").wait_for()

        await question.fill("What does that class syllabus say about the cafeteria menu?")
        await page.get_by_role("button", name="Ask Assistant").click()
        await page.get_by_text("did not refetch it").wait_for()

        await question.fill("What grading details are in that class syllabus for stale pending verification?")
        await page.get_by_role("button", name="Ask Assistant").click()
        await asyncio.wait_for(stale_started.wait(), timeout=3)
        await page.get_by_role("button", name="Reset source session").click()
        await asyncio.sleep(1.5)
        reset_ignored_stale = await page.locator("#conversational-response-card").count() == 0
        reset_cleared_scope = (
            await page.get_by_label("Source term").input_value() == ""
            and await page.get_by_label("Source section").input_value() == ""
        )

        await page.get_by_label("Source term").fill("202608")
        await page.get_by_label("Source section").fill("002")
        await question.fill("What does the grading section say for COP 4331?")
        await page.get_by_role("button", name="Ask Assistant").click()
        await page.get_by_text("Source Unavailable").wait_for()

        await browser.close()

    follow_up = next(item for item in response_log if item["message"].startswith("What are the learning outcomes"))
    fallback = next(item for item in response_log if "cafeteria" in item["message"])
    post_reset = response_log[-1]
    passed = all((
        response_log[0]["status"] == "grounded_answer",
        response_log[0]["citation_count"] > 0,
        follow_up["status"] == "grounded_answer",
        follow_up["additional_source_acquisitions"] == 0,
        follow_up["scope"] == {"course_code": "COP4331", "term_id": "202608", "section": "002"},
        fallback["response_code"] == "SESSION_EVIDENCE_INSUFFICIENT",
        fallback["additional_source_acquisitions"] == 0,
        reset_ignored_stale,
        reset_cleared_scope,
        post_reset["status"] == "acquisition_failed",
    ))
    return {
        "status": "passed" if passed else "failed",
        "verification_kind": "mocked_saved_evidence",
        "initial_answer": response_log[0],
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
        "SESSION_EVIDENCE_SIGNING_KEY": signing_key,
        "SYLLABUS_ACQUISITION_ENABLED": "false",
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
        source_url="https://fau.simplesyllabus.com/doc/sb4d8l8wb/COP-4331?mode=view",
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
        wait_http(f"{BACKEND_URL}/", [backend, frontend])
        wait_http(FRONTEND_URL, [backend, frontend])
        result = asyncio.run(verify(saved_record))
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "passed" else 1
    finally:
        stop_process(frontend)
        stop_process(backend)


if __name__ == "__main__":
    raise SystemExit(main())
