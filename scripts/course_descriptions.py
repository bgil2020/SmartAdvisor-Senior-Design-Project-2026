"""Manual CLI for the bounded FAU course-description workflow."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.course_descriptions.fetcher import FetchConfig, fetch_courses
from backend.course_descriptions.models import normalize_course_code, read_json
from backend.course_descriptions.storage import accept_batch, compare_batches, rollback_accepted, validate_batch
from backend.course_descriptions.workflow import parse_fetch_batch

DATA = ROOT / "data" / "course_descriptions"
RAW = DATA / "raw"
CANDIDATES = DATA / "candidates"
ACCEPTED = DATA / "accepted.json"
HISTORY = DATA / ".history"
SAMPLE_MANIFEST = DATA / "sample-manifest.json"


def show(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def default_batch_id() -> str:
    return datetime.now(timezone.utc).strftime("fau-%Y%m%dT%H%M%SZ")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="Show a no-network bounded collection plan")
    plan.add_argument("--courses", nargs="*")
    fetch = sub.add_parser("fetch", help="Fetch sitemap and bounded detail pages into ignored raw cache")
    fetch.add_argument("--courses", nargs="+", required=True)
    fetch.add_argument("--batch-id", default=None)
    fetch.add_argument("--pace-seconds", type=float, default=1.0)
    parse = sub.add_parser("parse", help="Parse one cached fetch batch offline")
    parse.add_argument("--batch-id", required=True)
    validate = sub.add_parser("validate", help="Validate a candidate batch offline")
    validate.add_argument("candidate", type=Path)
    compare = sub.add_parser("compare", help="Compare candidate content with accepted content")
    compare.add_argument("candidate", type=Path)
    accept = sub.add_parser("accept", help="Explicitly merge a valid partial candidate into accepted data")
    accept.add_argument("candidate", type=Path)
    rollback = sub.add_parser("rollback", help="Restore a prior locally saved accepted batch")
    rollback.add_argument("--batch-id", required=True)
    args = parser.parse_args()

    if args.command == "plan":
        manifest = read_json(SAMPLE_MANIFEST)
        courses = list(dict.fromkeys(normalize_course_code(value) for value in (args.courses or manifest["selected_courses"])))
        if not courses or len(courses) > 5:
            parser.error("plan requires between 1 and 5 unique course codes")
        show({"network": False, "courses": courses, "course_limit": 5, "request_budget": 3 * (1 + len(set(courses))), "requests": ["published sitemap", "one exact detail page per discovered course"], "accepted_data_will_change": False})
    elif args.command == "fetch":
        batch_id = args.batch_id or default_batch_id()
        show(fetch_courses(args.courses, cache_dir=RAW, batch_id=batch_id, config=FetchConfig(pace_seconds=args.pace_seconds)))
    elif args.command == "parse":
        candidate = CANDIDATES / f"{args.batch_id}.json"
        show(parse_fetch_batch(RAW / args.batch_id, candidate))
    elif args.command == "validate":
        result = validate_batch(read_json(args.candidate))
        show(result)
        return 0 if result["valid"] else 1
    elif args.command == "compare":
        show(compare_batches(read_json(ACCEPTED), read_json(args.candidate)))
    elif args.command == "accept":
        show(accept_batch(args.candidate, ACCEPTED, HISTORY))
    elif args.command == "rollback":
        show(rollback_accepted(ACCEPTED, HISTORY, args.batch_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
