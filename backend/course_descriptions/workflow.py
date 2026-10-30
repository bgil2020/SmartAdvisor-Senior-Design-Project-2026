"""Offline parse and candidate-batch assembly."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import SCHEMA_VERSION, read_json, utc_now, write_json
from .parser import ParseError, parse_course_detail


def parse_fetch_batch(fetch_dir: Path, candidate_path: Path) -> dict[str, Any]:
    manifest = read_json(fetch_dir / "fetch-manifest.json")
    records: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    for result in manifest.get("results", []):
        code, status = result.get("course_code"), result.get("status")
        if status != "fetched":
            outcomes.append({"course_code": code, "status": status, "error": result.get("error"), "http_status": result.get("http_status")})
            continue
        raw_path = Path(result["raw_evidence_ref"])
        try:
            record = parse_course_detail(
                raw_path.read_text(encoding="utf-8"), expected_course_code=code,
                source_url=result["source_url"], fetched_at=result["fetched_at"],
                raw_evidence_ref=result["raw_evidence_ref"], raw_sha256=result["raw_sha256"],
            )
        except ParseError as exc:
            status = "ambiguous" if exc.code == "ambiguous_description" else "rejected"
            outcomes.append({"course_code": code, "status": status, "error_code": exc.code, "error": str(exc)})
        else:
            records.append(record)
            outcomes.append({"course_code": code, "status": "parsed", "record_id": record["record_id"]})
    batch = {
        "schema_version": SCHEMA_VERSION,
        "batch_id": manifest["batch_id"],
        "delivery_mode": "partial",
        "created_at": utc_now(),
        "source_manifest": "data/course_descriptions/sample-manifest.json",
        "records": records,
        "outcomes": outcomes,
        "limitations": ["This bounded partial delivery does not represent the full FAU catalog."],
    }
    write_json(candidate_path, batch)
    return batch
