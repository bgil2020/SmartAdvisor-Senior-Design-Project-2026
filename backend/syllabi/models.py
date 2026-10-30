"""Syllabus record identity and content hashing."""
from __future__ import annotations

import re
from typing import Any

from backend.course_descriptions.models import normalize_course_code, sha256_text

PARSER_VERSION = "1.0"


def stable_syllabus_id(course_code: str, term_id: str, section: str, source_document_id: str) -> str:
    code = normalize_course_code(course_code).lower()
    safe = lambda value: re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    return f"fau-simple-syllabus:syllabus:{code}:{safe(term_id)}:{safe(section)}:{safe(source_document_id)}"


def syllabus_content_hash(record: dict[str, Any]) -> str:
    sections = record.get("academic_sections", [])
    payload = "\n".join(
        [
            str(record.get("course_code", "")),
            str(record.get("term_scope", {}).get("term_id", "")),
            str(record.get("section_scope", {}).get("section", "")),
            str(record.get("title", "")),
            str(record.get("document_text", "")),
            "\n".join(f"{item.get('heading', '')}\n{item.get('text', '')}" for item in sections),
        ]
    )
    return sha256_text(payload)
