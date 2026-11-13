"""Manual one-document Playwright collection for tracked syllabus identities.

Adapted from the peer's visible-browser prototype. This command performs one
anonymous navigation and writes ignored raw HTML only after the existing browser
guard classifies a complete rendered document. Parsing and acceptance remain in
``scripts/syllabi.py``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.course_descriptions.models import read_json
from backend.syllabi.browser_probe import BrowserProbeLimits, probe_browser_session
from backend.syllabi.playwright_driver import PlaywrightSession, classify_response_role

MANIFEST = ROOT / "data" / "syllabi" / "sample-manifest.json"
RAW = ROOT / "data" / "syllabi" / "raw"
DEFAULT_CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document-id", required=True, help="Document ID already present in data/syllabi/sample-manifest.json")
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--chrome", type=Path, default=DEFAULT_CHROME)
    parser.add_argument("--readiness-text", default="Course Evaluation Method")
    parser.add_argument("--deadline-seconds", type=float, default=20.0)
    parser.add_argument("--visible", action="store_true")
    args = parser.parse_args()
    documents = read_json(MANIFEST)["documents"]
    matches = [item for item in documents if item["source_document_id"] == args.document_id]
    if len(matches) != 1:
        parser.error("document ID must identify exactly one tracked manifest entry")
    if not args.chrome.is_file():
        parser.error("Chrome executable was not found; no browser runtime is downloaded automatically")
    item = matches[0]
    session = PlaywrightSession(chrome=args.chrome, document_id=args.document_id, readiness_text=args.readiness_text, visible=args.visible, deadline_seconds=args.deadline_seconds)
    result = probe_browser_session(session, item["view_url"], limits=BrowserProbeLimits())
    saved = None
    if result["status"] == "anonymous_full_document" and session.last_html:
        destination = RAW / args.batch_id / f"{args.document_id}.html"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(session.last_html, encoding="utf-8")
        saved = destination.relative_to(ROOT).as_posix()
    output = {
        "document": {key: item[key] for key in ("course_code", "term_id", "term_name", "section", "source_document_id", "view_url")},
        "probe": result,
        "final_url": session.final_url,
        "readiness_visible": session.readiness_visible,
        "saved_raw_evidence": saved,
        "response_counts": [
            {"role": role, "status": status, "count": count}
            for (role, status), count in sorted(session.observed.items())
        ],
    }
    print(json.dumps(output, indent=2))
    return 0 if saved else 2


if __name__ == "__main__":
    raise SystemExit(main())
