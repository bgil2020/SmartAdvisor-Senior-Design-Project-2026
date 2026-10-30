"""Validation, comparison, explicit acceptance, and rollback for batches."""
from __future__ import annotations

import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .models import BATCH_ID_RE, COURSE_RE, SCHEMA_VERSION, normalize_course_code, read_json, sha256_text, stable_record_id, utc_now, write_json

REQUIRED_RECORD_FIELDS = {
    "record_id", "record_version", "record_category", "course_code", "course_scope",
    "term_scope", "section_scope", "title", "description", "prerequisite_text",
    "exact_source_text", "source", "fetched_at", "collection_method",
    "raw_evidence_ref", "raw_sha256", "content_sha256", "parser_version",
    "schema_version", "unknowns", "limitations",
}


def validate_record(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["record must be an object"]
    missing = REQUIRED_RECORD_FIELDS - set(record)
    errors.extend(f"missing field: {field}" for field in sorted(missing))
    code = normalize_course_code(record.get("course_code", ""))
    if not COURSE_RE.fullmatch(code):
        errors.append("course_code has an invalid format")
    if record.get("record_id") != stable_record_id(code):
        errors.append("record_id is not the stable source/category/course identifier")
    if record.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"unsupported schema_version: {record.get('schema_version')}")
    if not isinstance(record.get("record_version"), int) or record.get("record_version", 0) < 1:
        errors.append("record_version must be an integer >= 1")
    if record.get("record_category") != "course_description":
        errors.append("record_category must be course_description")
    for field in ("title", "description", "exact_source_text"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            errors.append(f"{field} must be non-empty text")
    source = record.get("source")
    source_url = urlparse(str(source.get("url", ""))) if isinstance(source, dict) else None
    if source_url is None or source_url.scheme != "https" or source_url.hostname != "catalog.fau.edu" or not source_url.path.startswith("/courses/"):
        errors.append("source.url must be an allowed FAU course detail URL")
    expected_hash = sha256_text("\n".join([code, str(record.get("title", "")), str(record.get("description", "")), str(record.get("prerequisite_text") or "")]))
    if record.get("content_sha256") != expected_hash:
        errors.append("content_sha256 does not match normalized content")
    return errors


def validate_batch(batch: Any) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    if not isinstance(batch, dict):
        return {"valid": False, "errors": [{"path": "$", "message": "batch must be an object"}]}
    if batch.get("schema_version") != SCHEMA_VERSION:
        errors.append({"path": "$.schema_version", "message": "unsupported schema version"})
    if not isinstance(batch.get("batch_id"), str) or not BATCH_ID_RE.fullmatch(batch.get("batch_id", "")):
        errors.append({"path": "$.batch_id", "message": "batch_id must be a safe 3-80 character identifier"})
    records = batch.get("records")
    if not isinstance(records, list):
        errors.append({"path": "$.records", "message": "records must be an array"})
        records = []
    seen: set[str] = set()
    for index, record in enumerate(records):
        for message in validate_record(record):
            errors.append({"path": f"$.records[{index}]", "message": message})
        if isinstance(record, dict) and record.get("record_id") in seen:
            errors.append({"path": f"$.records[{index}].record_id", "message": "duplicate record ID"})
        elif isinstance(record, dict) and record.get("record_id"):
            seen.add(record["record_id"])
    return {"valid": not errors, "record_count": len(records), "errors": errors}


def _content_by_id(batch: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["record_id"]: item for item in batch.get("records", []) if isinstance(item, dict) and item.get("record_id")}


def compare_batches(accepted: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    old, new = _content_by_id(accepted), _content_by_id(candidate)
    result = {"added": [], "changed": [], "unchanged": [], "omitted": [], "not_found": [], "ambiguous": [], "failed": []}
    for record_id, record in new.items():
        if record_id not in old:
            result["added"].append(record_id)
        elif record.get("content_sha256") == old[record_id].get("content_sha256"):
            result["unchanged"].append(record_id)
        else:
            result["changed"].append(record_id)
    result["omitted"] = sorted(set(old) - set(new))
    for item in candidate.get("outcomes", []):
        status = item.get("status")
        if status in {"not_found", "ambiguous", "failed"}:
            result[status].append(item.get("course_code"))
    for key in result:
        result[key] = sorted(value for value in result[key] if value)
    result["omission_semantics"] = "Omitted accepted records remain accepted; partial deliveries never delete them."
    return result


def accept_batch(candidate_path: Path, accepted_path: Path, history_dir: Path) -> dict[str, Any]:
    candidate = read_json(candidate_path)
    validation = validate_batch(candidate)
    if not validation["valid"]:
        raise ValueError(f"Candidate is invalid: {validation['errors']}")
    accepted = read_json(accepted_path)
    old = _content_by_id(accepted)
    merged = deepcopy(old)
    for record in candidate.get("records", []):
        current = old.get(record["record_id"])
        updated = deepcopy(record)
        if current and current.get("content_sha256") == record.get("content_sha256"):
            updated = deepcopy(current)
        elif current:
            updated["record_version"] = current["record_version"] + 1
        else:
            updated["record_version"] = 1
        merged[updated["record_id"]] = updated
    previous_batch_id = accepted.get("accepted_batch_id") or "initial-empty"
    history_dir.mkdir(parents=True, exist_ok=True)
    history_path = history_dir / f"{previous_batch_id}.json"
    if not history_path.exists():
        shutil.copy2(accepted_path, history_path)
    output = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": "smartadvisor-course-descriptions",
        "accepted_batch_id": candidate["batch_id"],
        "accepted_at": utc_now(),
        "previous_accepted_batch_id": previous_batch_id,
        "records": sorted(merged.values(), key=lambda item: item["record_id"]),
    }
    write_json(accepted_path, output)
    return {"accepted_batch_id": candidate["batch_id"], "record_count": len(output["records"]), "rollback_snapshot": history_path.as_posix()}


def rollback_accepted(accepted_path: Path, history_dir: Path, batch_id: str) -> dict[str, Any]:
    if not BATCH_ID_RE.fullmatch(batch_id):
        raise ValueError("batch_id must be a safe 3-80 character identifier")
    snapshot = history_dir / f"{batch_id}.json"
    if not snapshot.exists():
        raise FileNotFoundError(f"Rollback snapshot not found: {snapshot}")
    current = read_json(accepted_path)
    current_id = current.get("accepted_batch_id") or "unknown"
    safety = history_dir / f"pre-rollback-{current_id}.json"
    if not safety.exists():
        shutil.copy2(accepted_path, safety)
    restored = read_json(snapshot)
    write_json(accepted_path, restored)
    return {"restored_batch_id": restored.get("accepted_batch_id"), "safety_snapshot": safety.as_posix()}
