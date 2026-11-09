"""Bounded, client-retained evidence for source-grounded session questions.

The server validates every returned record and authenticates the immutable source
identity/content tuple.  The browser owns retention; this module owns trust,
matching, chunking, retrieval, and deterministic fallback rendering.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
from dataclasses import dataclass
from typing import Any

from backend.course_descriptions.models import normalize_course_code
from backend.course_descriptions.storage import validate_record as validate_course_description
from backend.syllabi.storage import validate_record as validate_syllabus

MAX_RECORDS = 6
MAX_RECORD_BYTES = 120_000
MAX_TOTAL_BYTES = 300_000
MAX_CHUNK_CHARS = 3_500
MAX_RETRIEVED_CHUNKS = 3

_EPHEMERAL_KEY = secrets.token_bytes(32)


def _signing_key() -> bytes:
    configured = os.getenv("SESSION_EVIDENCE_SIGNING_KEY", "").strip()
    if configured and len(configured.encode("utf-8")) < 32:
        raise RuntimeError("SESSION_EVIDENCE_SIGNING_KEY must contain at least 32 bytes")
    return configured.encode("utf-8") if configured else _EPHEMERAL_KEY


def _proof_payload(record: dict[str, Any]) -> bytes:
    source = record.get("source") if isinstance(record.get("source"), dict) else {}
    value = {
        "record_id": record.get("record_id"),
        "record_category": record.get("record_category"),
        "course_code": normalize_course_code(record.get("course_code", "")),
        "term_id": (record.get("term_scope") or {}).get("term_id"),
        "section": (record.get("section_scope") or {}).get("section"),
        "source_id": source.get("source_id"),
        "source_url": source.get("url"),
        "content_sha256": record.get("content_sha256"),
    }
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def issue_provenance(record: dict[str, Any]) -> dict[str, str]:
    signature = hmac.new(_signing_key(), _proof_payload(record), hashlib.sha256).hexdigest()
    return {"scheme": "hmac-sha256-v1", "signature": signature}


def attach_provenance(record: dict[str, Any]) -> dict[str, Any]:
    result = dict(record)
    result["session_provenance"] = issue_provenance(record)
    return result


def _record_bytes(record: dict[str, Any]) -> int:
    return len(json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def validate_session_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Return only structurally valid, server-authenticated, bounded records."""
    if len(records) > MAX_RECORDS:
        return [], [f"evidence record limit exceeded ({MAX_RECORDS})"]
    accepted: list[dict[str, Any]] = []
    errors: list[str] = []
    total = 0
    seen: set[str] = set()
    for index, supplied in enumerate(records):
        if not isinstance(supplied, dict):
            errors.append(f"record {index} is not an object")
            continue
        size = _record_bytes(supplied)
        total += size
        if size > MAX_RECORD_BYTES:
            errors.append(f"record {index} exceeds the per-record byte limit")
            continue
        record = {key: value for key, value in supplied.items() if key != "session_provenance"}
        category = record.get("record_category")
        validation = validate_syllabus(record) if category == "syllabus" else (
            validate_course_description(record) if category == "course_description" else ["unsupported record category"]
        )
        provenance = supplied.get("session_provenance")
        expected = issue_provenance(record)
        if not isinstance(provenance, dict) or provenance.get("scheme") != expected["scheme"] or not hmac.compare_digest(str(provenance.get("signature", "")), expected["signature"]):
            validation.append("invalid or missing server provenance")
        record_id = str(record.get("record_id", ""))
        if record_id in seen:
            validation.append("duplicate record identity")
        if validation:
            errors.append(f"record {index}: {'; '.join(validation)}")
            continue
        seen.add(record_id)
        accepted.append(supplied)
    if total > MAX_TOTAL_BYTES:
        return [], [f"total evidence byte limit exceeded ({MAX_TOTAL_BYTES})"]
    return accepted, errors


def identity(record: dict[str, Any]) -> tuple[str, str | None, str | None, str]:
    return (
        normalize_course_code(record.get("course_code", "")),
        str((record.get("term_scope") or {}).get("term_id") or "") or None,
        str((record.get("section_scope") or {}).get("section") or "") or None,
        str(record.get("record_category", "")),
    )


def matching_records(records: list[dict[str, Any]], *, course_code: str, term_id: str | None, section: str | None) -> list[dict[str, Any]]:
    code = normalize_course_code(course_code)
    result = []
    for record in records:
        rec_code, rec_term, rec_section, category = identity(record)
        if rec_code != code:
            continue
        if category == "syllabus":
            if term_id and rec_term != str(term_id):
                continue
            if section and rec_section != str(section):
                continue
        result.append(record)
    return result


def resolve_scope(message: str, explicit_courses: list[str], records: list[dict[str, Any]], context: dict[str, Any] | None) -> tuple[dict[str, str | None] | None, str | None]:
    """Resolve explicit identity or a singular contextual reference such as 'that class'."""
    context = context or {}
    courses = list(dict.fromkeys(normalize_course_code(item) for item in explicit_courses if item))
    contextual = bool(re.search(r"\b(that|this|the)\s+(class|course|section)\b|\bit\b", message, re.I))
    if not courses and context.get("course_code"):
        courses = [normalize_course_code(context["course_code"])]
    if not courses and contextual:
        courses = list(dict.fromkeys(identity(item)[0] for item in records))
    if len(courses) != 1:
        return None, "Please specify the course code" if not courses else "Please specify which course you mean"
    course = courses[0]
    term = str(context.get("term_id") or "") or None
    section = str(context.get("section") or "") or None
    syllabus_scopes = {(identity(item)[1], identity(item)[2]) for item in records if identity(item)[0] == course and identity(item)[3] == "syllabus"}
    if not term and len({item[0] for item in syllabus_scopes}) == 1:
        term = next(iter(syllabus_scopes))[0]
    if not section and term:
        sections = {item[1] for item in syllabus_scopes if item[0] == term}
        if len(sections) == 1:
            section = next(iter(sections))
    if contextual and len(syllabus_scopes) > 1 and (not term or not section):
        return None, "Please specify the term and section because more than one syllabus matches that class"
    return {"course_code": course, "term_id": term, "section": section}, None


@dataclass(frozen=True)
class Chunk:
    text: str
    heading: str
    citation: dict[str, Any]
    score: int


def retrieve(message: str, records: list[dict[str, Any]]) -> list[Chunk]:
    query_terms = {term for term in re.findall(r"[a-z0-9]+", message.casefold()) if len(term) > 2}
    chunks: list[Chunk] = []
    for record in records:
        source = record.get("source") or {}
        if record.get("record_category") == "syllabus":
            sections = record.get("academic_sections") or []
        else:
            sections = [
                {"heading": "Course description", "text": record.get("description", ""), "locator": "field:description"},
                {"heading": "Prerequisites", "text": record.get("prerequisite_text", ""), "locator": "field:prerequisite_text"},
            ]
        for item in sections:
            text = str(item.get("text", "")).strip()[:MAX_CHUNK_CHARS]
            if not text:
                continue
            terms = set(re.findall(r"[a-z0-9]+", f"{item.get('heading', '')} {text}".casefold()))
            score = len(query_terms & terms)
            chunks.append(Chunk(text=text, heading=str(item.get("heading", "Source excerpt")), score=score, citation={
                "record_id": record.get("record_id"), "title": source.get("title") or record.get("title"),
                "url": source.get("url"), "locator": item.get("locator"),
                "course_code": record.get("course_code"), "term_id": (record.get("term_scope") or {}).get("term_id"),
                "section": (record.get("section_scope") or {}).get("section"),
            }))
    ranked = sorted(chunks, key=lambda item: (-item.score, item.heading.casefold()))
    positive = [item for item in ranked if item.score > 0]
    return positive[:MAX_RETRIEVED_CHUNKS]


def deterministic_answer(message: str, records: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]], bool]:
    chunks = retrieve(message, records)
    if not chunks:
        return "The matching source is already in this session, but it does not contain enough clearly matching information to answer that question. I did not refetch it.", [], True
    excerpts = []
    citations = []
    for index, chunk in enumerate(chunks, 1):
        compact = re.sub(r"\s+", " ", chunk.text).strip()
        excerpts.append(f"[{index}] {chunk.heading}: {compact[:700]}")
        citation = dict(chunk.citation)
        citation["index"] = index
        citations.append(citation)
    return "Based on the matching session source:\n\n" + "\n\n".join(excerpts), citations, True
