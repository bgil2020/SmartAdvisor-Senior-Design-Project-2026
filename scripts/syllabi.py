"""Manual, bounded FAU Simple Syllabus probe and offline-import CLI."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from backend.course_descriptions.http import FetchConfig
from backend.course_descriptions.models import read_json
from backend.course_descriptions.storage import compare_batches
from backend.syllabi.probe import probe_documents
from backend.syllabi.storage import accept_batch, rollback_accepted, validate_batch
from backend.syllabi.workflow import parse_offline_batch

DATA = ROOT / "data" / "syllabi"
MANIFEST = DATA / "sample-manifest.json"
RAW = DATA / "raw"
CANDIDATES = DATA / "candidates"
ACCEPTED = DATA / "accepted.json"
HISTORY = DATA / ".history"


def show(value: object) -> None: print(json.dumps(value, indent=2, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan", help="Show tracked document identities without network access")
    probe = sub.add_parser("probe", help="Probe at most three visible document URLs; does not collect text")
    probe.add_argument("--pace-seconds", type=float, default=1.0)
    parse = sub.add_parser("parse", help="Parse manually supplied permitted rendered HTML offline")
    parse.add_argument("--batch-id", required=True)
    validate = sub.add_parser("validate"); validate.add_argument("candidate", type=Path)
    compare = sub.add_parser("compare"); compare.add_argument("candidate", type=Path)
    accept = sub.add_parser("accept"); accept.add_argument("candidate", type=Path)
    rollback = sub.add_parser("rollback"); rollback.add_argument("--batch-id", required=True)
    args = parser.parse_args()
    documents = read_json(MANIFEST)["documents"]
    if args.command == "plan":
        show({"network": False, "document_limit": 3, "documents": documents, "accepted_data_will_change": False})
    elif args.command == "probe":
        show(probe_documents(documents, config=FetchConfig(pace_seconds=args.pace_seconds, max_retries=1)))
    elif args.command == "parse":
        show(parse_offline_batch(MANIFEST, RAW / args.batch_id, CANDIDATES / f"{args.batch_id}.json", args.batch_id))
    elif args.command == "validate":
        result = validate_batch(read_json(args.candidate)); show(result); return 0 if result["valid"] else 1
    elif args.command == "compare": show(compare_batches(read_json(ACCEPTED), read_json(args.candidate)))
    elif args.command == "accept": show(accept_batch(args.candidate, ACCEPTED, HISTORY))
    elif args.command == "rollback": show(rollback_accepted(ACCEPTED, HISTORY, args.batch_id))
    return 0


if __name__ == "__main__": raise SystemExit(main())
