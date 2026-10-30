"""Offline candidate assembly from explicitly supplied permitted HTML."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.course_descriptions.models import SCHEMA_VERSION, read_json, utc_now, write_json
from .parser import SyllabusParseError, parse_rendered_syllabus


def parse_offline_batch(manifest_path: Path, raw_dir: Path, candidate_path: Path, batch_id: str) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    records, outcomes = [], []
    for item in manifest["documents"]:
        raw_path = raw_dir / f"{item['source_document_id']}.html"
        if not raw_path.exists():
            outcomes.append({"course_code": item["course_code"], "source_document_id": item["source_document_id"], "status": item.get("observed_access", "not_found")})
            continue
        try:
            record = parse_rendered_syllabus(raw_path.read_text(encoding="utf-8"), course_code=item["course_code"], term_id=item["term_id"], term_name=item["term_name"], section=item["section"], source_document_id=item["source_document_id"], source_url=item["view_url"], fetched_at=utc_now(), raw_evidence_ref=raw_path.as_posix(), instructor=item.get("instructor"))
        except SyllabusParseError as exc:
            outcomes.append({"course_code": item["course_code"], "source_document_id": item["source_document_id"], "status": "ambiguous", "error_code": exc.code})
        else:
            records.append(record)
            outcomes.append({"course_code": item["course_code"], "source_document_id": item["source_document_id"], "status": "parsed", "record_id": record["record_id"]})
    batch = {"schema_version": SCHEMA_VERSION, "batch_id": batch_id, "delivery_mode": "partial", "created_at": utc_now(), "source_manifest": manifest_path.as_posix(), "records": records, "outcomes": outcomes, "limitations": ["Missing or restricted documents remain outcomes and never delete accepted records."]}
    write_json(candidate_path, batch)
    return batch
