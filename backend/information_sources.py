"""Read-only inventory of exact, approved informational source mappings."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from backend.course_descriptions.models import normalize_course_code

ROOT = Path(__file__).resolve().parents[1]
COURSE_DESCRIPTION_MANIFEST = ROOT / "data" / "course_descriptions" / "sample-manifest.json"
SYLLABUS_MANIFEST = ROOT / "data" / "syllabi" / "sample-manifest.json"


@lru_cache(maxsize=4)
def approved_information_sources(
    course_description_manifest: Path = COURSE_DESCRIPTION_MANIFEST,
    syllabus_manifest: Path = SYLLABUS_MANIFEST,
) -> dict[str, tuple[str, ...]]:
    """Return source categories backed by exact tracked mappings, without fetching them."""
    categories: dict[str, set[str]] = {}
    descriptions = json.loads(course_description_manifest.read_text(encoding="utf-8"))
    selected = {normalize_course_code(code) for code in descriptions.get("selected_courses", [])}
    for code, url in (descriptions.get("detail_urls_discovered_from_published_sitemap") or {}).items():
        normalized = normalize_course_code(code)
        if normalized in selected and isinstance(url, str) and url.startswith("https://catalog.fau.edu/courses/"):
            categories.setdefault(normalized, set()).add("course_description")

    syllabi = json.loads(syllabus_manifest.read_text(encoding="utf-8"))
    for document in syllabi.get("documents", []):
        code = normalize_course_code(document.get("course_code", ""))
        url = document.get("view_url")
        if code and isinstance(url, str) and url.startswith("https://fau.simplesyllabus.com/"):
            categories.setdefault(code, set()).add("syllabus")

    order = {"course_description": 0, "syllabus": 1}
    return {code: tuple(sorted(values, key=order.__getitem__)) for code, values in categories.items()}
