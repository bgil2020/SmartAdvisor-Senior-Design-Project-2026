"""Canonical course-description record helpers.

The stable record ID identifies a source/course/category tuple. Content hashes
identify revisions and therefore must never be used as record IDs.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
RECORD_VERSION = 1
PARSER_VERSION = "1.0"
COURSE_RE = re.compile(r"^[A-Z]{3}\d{4}[A-Z]?$")
BATCH_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$")


def normalize_course_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def stable_record_id(course_code: str, category: str = "course_description") -> str:
    code = normalize_course_code(course_code)
    return f"fau-catalog:{category}:{code.lower()}"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
