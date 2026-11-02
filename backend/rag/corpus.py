"""Validated source-record import and deterministic chunk construction."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.course_descriptions.models import read_json, utc_now, write_json
from backend.course_descriptions.storage import validate_batch as validate_course_batch
from backend.syllabi.storage import validate_batch as validate_syllabus_batch

CORPUS_VERSION = "1.0"
SYLLABUS_EXCLUDED_HEADINGS = {
    "instructor information",
    "code of academic integrity",
    "policy on the recording of lectures",
    "artificial intelligence preamble",
}


def _source_version(record: dict[str, Any]) -> str:
    return f"{record.get('record_version', 1)}:{record.get('content_sha256', '')}"


def _chunk_id(document_id: str, locator: str, content_sha256: str) -> str:
    digest = hashlib.sha256(f"{document_id}\n{locator}\n{content_sha256}".encode()).hexdigest()[:16]
    return f"rag:{digest}"


def chunks_from_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    category = record["record_category"]
    source = record["source"]
    common = {
        "document_id": record["record_id"],
        "source_version": _source_version(record),
        "record_category": category,
        "course_code": record["course_code"],
        "term_id": (record.get("term_scope") or {}).get("term_id"),
        "term_name": (record.get("term_scope") or {}).get("term_name"),
        "section": (record.get("section_scope") or {}).get("section"),
        "title": record["title"],
        "source_url": source["url"],
        "content_sha256": record["content_sha256"],
        "limitations": list(record.get("limitations", [])),
    }
    passages: list[tuple[str, str]] = []
    if category == "course_description":
        passages.append(("Course Description", record["description"]))
        if record.get("prerequisite_text"):
            passages.append(("Prerequisites", record["prerequisite_text"]))
    elif category == "syllabus":
        for section in record.get("academic_sections", []):
            heading = str(section.get("heading", "")).strip().casefold()
            if heading in SYLLABUS_EXCLUDED_HEADINGS:
                continue
            passages.append((section["locator"], section["text"]))
    else:
        raise ValueError(f"Unsupported source category: {category}")

    return [
        {
            **common,
            "chunk_id": _chunk_id(record["record_id"], locator, record["content_sha256"]),
            "locator": locator,
            "text": text.strip(),
        }
        for locator, text in passages
        if text and text.strip()
    ]


def import_validated_corpus(
    *,
    course_batches: list[Path],
    syllabus_batches: list[Path],
    output_path: Path,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    inputs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for category, paths, validator in (
        ("course_description", course_batches, validate_course_batch),
        ("syllabus", syllabus_batches, validate_syllabus_batch),
    ):
        for path in paths:
            batch = read_json(path)
            validation = validator(batch)
            if not validation["valid"]:
                raise ValueError(f"Invalid {category} batch {path}: {validation['errors']}")
            for record in batch.get("records", []):
                if record["record_id"] in seen:
                    raise ValueError(f"Duplicate source record: {record['record_id']}")
                seen.add(record["record_id"])
                records.append(record)
            inputs.append({"category": category, "path": path.as_posix(), "batch_id": batch.get("batch_id") or batch.get("accepted_batch_id"), "record_count": len(batch.get("records", []))})

    chunks = [chunk for record in records for chunk in chunks_from_record(record)]
    output = {
        "corpus_version": CORPUS_VERSION,
        "created_at": utc_now(),
        "acceptance": "Locally validated explicit import; redistribution in Git is not authorized by this artifact.",
        "inputs": inputs,
        "document_count": len(records),
        "chunk_count": len(chunks),
        "course_coverage": sorted({record["course_code"] for record in records}),
        "syllabus_coverage": [
            {"course_code": record["course_code"], "term": record["term_scope"], "section": record["section_scope"]}
            for record in records if record["record_category"] == "syllabus"
        ],
        "chunks": chunks,
    }
    write_json(output_path, output)
    return {key: output[key] for key in ("document_count", "chunk_count", "course_coverage", "syllabus_coverage")}


def load_corpus(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("corpus_version") != CORPUS_VERSION or not isinstance(value.get("chunks"), list):
        raise ValueError("Unsupported or malformed RAG corpus")
    return value
