"""One-request live Gemini verification through the newer chatbot UI.

This harness is intentionally inert unless the explicit approval flag is
present. It loads the approved public COP 4331 fixture, signs it with the
normal session-evidence mechanism, and submits exactly one UI question.
It never enables catalog or syllabus acquisition.
"""
from __future__ import annotations

import argparse
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
MODEL = "gemini-3.5-flash-lite"
SCREENSHOT = ROOT / "docs" / "ui-verification" / "live-gemini-chatbot.png"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


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
    require(browser_path is not None, "No installed Chrome or Edge executable is available")

    conversation_requests = 0
    observed_response: dict | None = None
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, executable_path=str(browser_path))
        page = await browser.new_page(viewport={"width": 1440, "height": 1100})

        async def attach_fixture(route, request):
            nonlocal conversation_requests, observed_response
            conversation_requests += 1
            require(conversation_requests == 1, "Unexpected additional /conversation request")
            body = request.post_data_json
            body["session_evidence"] = [saved_record]
            body["session_context"] = {
                "course_code": "COP4331",
                "term_id": "202608",
                "section": "002",
            }
            upstream = await route.fetch(post_data=json.dumps(body))
            observed_response = await upstream.json()
            await route.fulfill(response=upstream)

        await page.route(f"{BACKEND_URL}/conversation", attach_fixture)
        try:
            await page.goto(FRONTEND_URL, wait_until="networkidle")
            await page.get_by_role("button", name="Open SmartAdvisor Chat").click()
            require(page.url.endswith("/chatbot"), "Home did not navigate to /chatbot")
            composer = page.get_by_label("Student Question or Planning Query:")
            await composer.fill("What does the grading section say for COP 4331?")
            await page.get_by_role("button", name="Send", exact=True).click()
            await page.get_by_text("Live generation: Accepted Gemini answer", exact=False).wait_for(timeout=45_000)
            await page.get_by_role("list", name="Source citations").wait_for()
            require(observed_response is not None, "No /conversation response was observed")
            require(observed_response.get("generation_source") == "provider", "Answer was not accepted provider generation")
            require(observed_response.get("generation_fallback_used") is False, "Answer used fallback")
            require(observed_response.get("model_id") == MODEL, "Unexpected generation model")
            citations = observed_response.get("citations") or []
            require(bool(citations), "Accepted answer had no citation")
            source_id = citations[0].get("source_id")
            require(bool(source_id) and source_id in observed_response.get("response_text", ""), "Answer did not cite its validated source ID")
            SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=SCREENSHOT, full_page=True)
            return {
                "status": "passed",
                "provider": "Google Gemini Developer API",
                "model_id": observed_response.get("model_id"),
                "generation_source": observed_response.get("generation_source"),
                "generation_fallback_used": observed_response.get("generation_fallback_used"),
                "citation_count": len(citations),
                "conversation_requests": conversation_requests,
                "provider_request_budget": 1,
                "screenshot": str(SCREENSHOT),
            }
        finally:
            await browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--approved-live-gemini", action="store_true")
    args = parser.parse_args()
    require(args.approved_live_gemini, "Live Gemini verification requires explicit approval and --approved-live-gemini")
    require(bool(os.getenv("GEMINI_API_KEY", "").strip()), "GEMINI_API_KEY is not present")

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
        "SYLLABUS_ACQUISITION_ENABLED": "false",
        "SMARTADVISOR_CORS_ORIGINS": FRONTEND_URL,
        "VITE_API_URL": BACKEND_URL,
    })
    os.environ.update(environment)

    from backend.course_descriptions.models import utc_now
    from backend.session_evidence import attach_provenance
    from backend.syllabi.parser import parse_rendered_syllabus

    fixture = ROOT / "tests" / "syllabi" / "fixtures" / "rendered_complete.html"
    record = parse_rendered_syllabus(
        fixture.read_text(encoding="utf-8"),
        course_code="COP4331",
        term_id="202608",
        term_name="Fall 2026 1 Full Term",
        section="002",
        source_document_id="sb4d8l8wb",
        source_url="https://fau.simplesyllabus.com/en-US/doc/sb4d8l8wb/Fall-2026-1-Full-Term-COP-4331-002-Object-Oriented-Design-%26-Prog?mode=view",
        fetched_at=utc_now(),
        raw_evidence_ref="session-memory:bounded-live-gemini-ui",
    )
    saved_record = attach_provenance(record)
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.api:app", "--host", "127.0.0.1", "--port", "18100", "--workers", "1"],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    frontend = subprocess.Popen(
        ["node", str(ROOT / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"), "--host", "127.0.0.1", "--port", "14173"],
        cwd=ROOT / "frontend",
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_http(f"{BACKEND_URL}/health", [backend, frontend])
        wait_http(FRONTEND_URL, [backend, frontend])
        print(json.dumps(asyncio.run(verify(saved_record)), sort_keys=True))
        return 0
    finally:
        stop_process(frontend)
        stop_process(backend)


if __name__ == "__main__":
    raise SystemExit(main())
