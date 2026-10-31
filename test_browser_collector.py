from datetime import datetime, timezone
from playwright.sync_api import sync_playwright
from backend.syllabi.parser import parse_rendered_syllabus
from workload_analysis import analyze_workload


def collect_syllabus(course_code, section, term_id, term_name, document_id, url):
    """Retrieve and parse a publicly accessible FAU syllabus."""

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)

        try:
            page = browser.new_page()
            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000
            )

            status = response.status if response else None
            print("HTTP status:", status)

            if status in (401, 403, 429):
                print("Access restricted. Collection stopped.")
                return None

            if status != 200:
                print("Unexpected HTTP response. Collection stopped.")
                return None

            # Wait for the academic content to appear.
            page.get_by_text(
                "Course Evaluation Method",
                exact=True
            ).first.wait_for(timeout=15000)

            html = page.content()

            result = parse_rendered_syllabus(
                html,
                course_code=course_code,
                term_id=term_id,
                term_name=term_name,
                section=section,
                source_document_id=document_id,
                source_url=url,
                fetched_at=datetime.now(timezone.utc).isoformat(),
                raw_evidence_ref="browser_test"
            )

            return result

        finally:
            browser.close()


if __name__ == "__main__":

    syllabus = collect_syllabus(
        course_code="EEL3111",
        section="001",
        term_id="202608",
        term_name="Fall 2026",
        document_id="a4bh2nqsq",
        url="https://fau.simplesyllabus.com/en-US/doc/a4bh2nqsq/Fall-2026-1-Full-Term-EEL-3111-001-Circuits-1?mode=view"
    )

    if syllabus:
        print("\nCourse:", syllabus["course_code"])
        print("Sections extracted:", len(syllabus["academic_sections"]))

        for section in syllabus["academic_sections"]:
            print("-", section["heading"])

            if section["heading"] == "Course Evaluation Method":
                print("\nGRADING INFORMATION:")
                print(section)

                workload = analyze_workload(section["text"])
                print("\nWORKLOAD ANALYSIS:", workload)