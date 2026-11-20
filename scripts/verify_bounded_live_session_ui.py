"""Approved-only live UI check with fail-fast acquisition assertions.

Run only after the operator has approved the two exact mapped sources and the
backend was started with both ACQUISITION_TEST_*_BUDGET values set to 1.
The backend budget is authoritative: an attempted second source acquisition
fails before transport/browser startup. This driver also stops immediately
after any unexpected acquisition response, before submitting the next step.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

FRONTEND_URL = "http://127.0.0.1:14173"
BACKEND_URL = "http://127.0.0.1:18100"
EXPECTED_SCOPE = {"course_code": "COP4331", "term_id": "202608", "section": "002"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


async def main() -> None:
    from playwright.async_api import async_playwright

    chrome = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    require(chrome.exists(), f"Installed Chrome not found: {chrome}")
    responses: list[dict] = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False, executable_path=str(chrome))
        page = await browser.new_page()

        async def observe(route, request):
            upstream = await route.fetch()
            payload = await upstream.json()
            responses.append(payload)
            await route.fulfill(response=upstream)

        await page.route(f"{BACKEND_URL}/conversation", observe)
        try:
            await page.goto(FRONTEND_URL, wait_until="networkidle")
            await page.get_by_role("button", name="Go to Forms & Engines").click()
            await page.get_by_role("button", name="AI Assistant Chat").click()
            question = page.get_by_label("Student Question or Planning Query:")

            async def ask(text: str) -> dict:
                before = len(responses)
                await question.fill(text)
                await page.get_by_role("button", name="Ask Assistant").click()
                while len(responses) == before:
                    await page.wait_for_timeout(50)
                return responses[-1]

            catalog = await ask("What is the course description for COP 4331?")
            catalog_acq = catalog.get("acquisition") or {}
            require(catalog.get("status") == "grounded_answer", f"Catalog failed: {catalog.get('status')}")
            require(catalog_acq.get("status") == "acquired", f"Catalog was not acquired: {catalog_acq}")
            require(catalog_acq.get("additional_source_acquisitions") == 1, f"Catalog count mismatch: {catalog_acq}")
            require((catalog_acq.get("test_budget") or {}).get("limit") == 1, "Catalog test budget was not enforced")

            await page.get_by_label("Source term").fill("202608")
            await page.get_by_label("Source section").fill("002")
            syllabus = await ask("What does the grading section say for COP 4331?")
            syllabus_acq = syllabus.get("acquisition") or {}
            require(syllabus.get("status") == "grounded_answer", f"Syllabus failed: {syllabus.get('status')}")
            require(syllabus_acq.get("status") == "acquired", f"Syllabus was not acquired: {syllabus_acq}")
            require(syllabus_acq.get("additional_source_acquisitions") == 1, f"Syllabus count mismatch: {syllabus_acq}")
            require((syllabus_acq.get("test_budget") or {}).get("limit") == 1, "Syllabus test budget was not enforced")
            require(syllabus.get("source_scope") == EXPECTED_SCOPE, f"Syllabus scope mismatch: {syllabus.get('source_scope')}")
            require(bool(syllabus.get("citations")), "Syllabus answer had no citation")

            follow_up = await ask("What are the learning outcomes for that class?")
            follow_acq = follow_up.get("acquisition") or {}
            require(follow_acq.get("status") == "not_needed", f"Follow-up attempted acquisition: {follow_acq}")
            require(follow_acq.get("additional_source_acquisitions") == 0, f"Follow-up count mismatch: {follow_acq}")
            require(follow_up.get("status") == "grounded_answer" and bool(follow_up.get("citations")), "Follow-up was not grounded")

            missing = await ask("What does that class syllabus say about the cafeteria menu?")
            missing_acq = missing.get("acquisition") or {}
            require(missing_acq.get("status") == "not_needed", f"Missing-detail check attempted acquisition: {missing_acq}")
            require(missing_acq.get("additional_source_acquisitions") == 0, f"Missing-detail count mismatch: {missing_acq}")
            require(missing.get("response_code") == "SESSION_EVIDENCE_INSUFFICIENT", f"Missing-detail result was unsafe: {missing.get('response_code')}")

            await page.get_by_role("button", name="Reset source session").click()
            require(await page.get_by_label("Source term").input_value() == "", "Reset did not clear term")
            require(await page.get_by_label("Source section").input_value() == "", "Reset did not clear section")
            print(json.dumps({
                "status": "passed",
                "catalog": catalog_acq,
                "syllabus": syllabus_acq,
                "follow_up": follow_acq,
                "missing_detail": {"response_code": missing.get("response_code"), "acquisition": missing_acq},
                "reset": "passed",
            }, sort_keys=True))
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
