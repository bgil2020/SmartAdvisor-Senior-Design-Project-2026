"""Syllabus validation using the shared candidate/accepted lifecycle."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from backend.course_descriptions.models import BATCH_ID_RE, COURSE_RE, SCHEMA_VERSION, normalize_course_code
from backend.course_descriptions.storage import accept_batch as shared_accept_batch
from backend.course_descriptions.storage import compare_batches, rollback_accepted
from .models import stable_syllabus_id, syllabus_content_hash

REQUIRED = {
    "record_id", "record_version", "record_category", "course_code", "course_scope",
    "term_scope", "section_scope", "title", "document_version", "instructor",
    "document_text", "exact_source_text", "academic_sections", "source", "fetched_at",
    "published_at", "updated_at", "observed_access", "collection_method",
    "raw_evidence_ref", "raw_sha256", "content_sha256", "parser_version",
    "schema_version", "unknowns", "limitations",
}


def validate_record(record: Any) -> list[str]:
    if not isinstance(record, dict):
        return ["record must be an object"]
    errors = [f"missing field: {field}" for field in sorted(REQUIRED - set(record))]
    code = normalize_course_code(record.get("course_code", ""))
    term = record.get("term_scope") if isinstance(record.get("term_scope"), dict) else {}
    section = record.get("section_scope") if isinstance(record.get("section_scope"), dict) else {}
    source = record.get("source") if isinstance(record.get("source"), dict) else {}
    if not COURSE_RE.fullmatch(code): errors.append("course_code has an invalid format")
    if not term.get("term_id") or not term.get("term_name"): errors.append("term_scope must preserve term_id and term_name")
    if not section.get("section"): errors.append("section_scope must preserve section")
    expected_id = stable_syllabus_id(code, term.get("term_id", ""), section.get("section", ""), source.get("source_id", ""))
    if record.get("record_id") != expected_id: errors.append("record_id is not the stable document/course/term/section identifier")
    if record.get("record_category") != "syllabus": errors.append("record_category must be syllabus")
    if record.get("schema_version") != SCHEMA_VERSION: errors.append("unsupported schema_version")
    if not isinstance(record.get("record_version"), int) or record.get("record_version", 0) < 1: errors.append("record_version must be an integer >= 1")
    for field in ("title", "document_text", "exact_source_text"):
        if not isinstance(record.get(field), str) or not record[field].strip(): errors.append(f"{field} must be non-empty text")
    parsed = urlparse(str(source.get("url", "")))
    if parsed.scheme != "https" or parsed.hostname != "fau.simplesyllabus.com" or not parsed.path.startswith("/doc/"):
        errors.append("source.url must be an allowed FAU Simple Syllabus document URL")
    sections = record.get("academic_sections")
    if not isinstance(sections, list) or not sections or any(not isinstance(item, dict) or not item.get("heading") or not item.get("text") or not item.get("locator") for item in sections):
        errors.append("academic_sections must contain located, non-empty sections")
    if record.get("content_sha256") != syllabus_content_hash(record): errors.append("content_sha256 does not match normalized content")
    return errors


def validate_batch(batch: Any) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    if not isinstance(batch, dict): return {"valid": False, "errors": [{"path": "$", "message": "batch must be an object"}]}
    if batch.get("schema_version") != SCHEMA_VERSION: errors.append({"path": "$.schema_version", "message": "unsupported schema version"})
    if not isinstance(batch.get("batch_id"), str) or not BATCH_ID_RE.fullmatch(batch.get("batch_id", "")): errors.append({"path": "$.batch_id", "message": "batch_id must be safe"})
    records = batch.get("records")
    if not isinstance(records, list): errors.append({"path": "$.records", "message": "records must be an array"}); records = []
    seen: set[str] = set()
    for index, record in enumerate(records):
        for message in validate_record(record): errors.append({"path": f"$.records[{index}]", "message": message})
        record_id = record.get("record_id") if isinstance(record, dict) else None
        if record_id in seen: errors.append({"path": f"$.records[{index}].record_id", "message": "duplicate record ID"})
        if record_id: seen.add(record_id)
    return {"valid": not errors, "record_count": len(records), "errors": errors}


def accept_batch(candidate_path: Path, accepted_path: Path, history_dir: Path) -> dict[str, Any]:
    return shared_accept_batch(candidate_path, accepted_path, history_dir, validator=validate_batch, dataset_id="smartadvisor-syllabi")

__all__ = ["accept_batch", "compare_batches", "rollback_accepted", "validate_batch", "validate_record"]
