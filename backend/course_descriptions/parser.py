"""Deterministic parser for server-rendered FAU catalog detail pages."""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

from .models import PARSER_VERSION, RECORD_VERSION, SCHEMA_VERSION, normalize_course_code, sha256_text, stable_record_id


class ParseError(ValueError):
    """A page cannot be safely identified as one unambiguous course detail."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class _DetailParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, dict[str, str]]] = []
        self.course_headings: list[str] = []
        self.title_candidates: list[str] = []
        self.description_values: list[str] = []
        self._capture: str | None = None
        self._buffer: list[str] = []
        self._pending_description = False

    @staticmethod
    def _classes(attrs: dict[str, str]) -> set[str]:
        return set(attrs.get("class", "").split())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        if tag != "br":
            self.stack.append((tag, attr))
        classes = self._classes(attr)
        if tag == "h1" and {"heading-1", "mb-2"}.issubset(classes):
            self._capture, self._buffer = "course", []
        elif tag == "h2" and {"heading-5", "mb-2"}.issubset(classes):
            self._capture, self._buffer = "title", []
        elif tag == "h3" and "field-label" in classes:
            self._capture, self._buffer = "label", []
        elif tag == "div" and "field-value" in classes and self._pending_description:
            self._capture, self._buffer = "description", []
            self._pending_description = False
        elif tag == "br" and self._capture == "description":
            self._buffer.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self._capture and self.stack and self.stack[-1][0] == tag:
            value = _clean_text("".join(self._buffer), preserve_lines=self._capture == "description")
            if self._capture == "course" and value:
                self.course_headings.append(value)
            elif self._capture == "title" and value and value != "Download as PDF":
                self.title_candidates.append(value)
            elif self._capture == "label":
                self._pending_description = value.casefold() == "course description"
            elif self._capture == "description" and value:
                self.description_values.append(value)
            self._capture, self._buffer = None, []
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer.append(data)


def _clean_text(value: str, *, preserve_lines: bool = False) -> str:
    value = html.unescape(value).replace("\xa0", " ").replace("\r", "")
    if preserve_lines:
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.split("\n")]
        return "\n".join(line for line in lines if line)
    return re.sub(r"\s+", " ", value).strip()


def _split_description(value: str, title: str) -> tuple[str, str | None, str]:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if lines and lines[0].casefold() == title.casefold():
        lines.pop(0)
    prerequisites: list[str] = []
    description: list[str] = []
    for line in lines:
        if re.match(r"^prerequisites?(?:\s+or\s+corequisites?)?\s*:", line, flags=re.IGNORECASE):
            prerequisites.append(line)
        else:
            description.append(line)
    if not description:
        raise ParseError("missing_description", "No descriptive passage remains after structured fields")
    return "\n".join(description), "\n".join(prerequisites) or None, value


def parse_course_detail(
    html_text: str,
    *,
    expected_course_code: str,
    source_url: str,
    fetched_at: str,
    raw_evidence_ref: str,
    raw_sha256: str | None = None,
) -> dict[str, Any]:
    expected = normalize_course_code(expected_course_code)
    if urlparse(source_url).hostname != "catalog.fau.edu":
        raise ParseError("source_not_allowed", "Source URL is outside catalog.fau.edu")
    parser = _DetailParser()
    parser.feed(html_text)
    codes = {normalize_course_code(item) for item in parser.course_headings}
    if expected not in codes or len(codes) != 1:
        raise ParseError("course_identity_mismatch", f"Expected {expected}; detail headings were {sorted(codes)}")
    if len(parser.description_values) != 1:
        code = "missing_description" if not parser.description_values else "ambiguous_description"
        raise ParseError(code, f"Expected one Course Description field; found {len(parser.description_values)}")
    if not parser.title_candidates:
        raise ParseError("missing_title", "Course title was not found")
    title = parser.title_candidates[0]
    description, prerequisite, exact_source_text = _split_description(parser.description_values[0], title)
    return {
        "record_id": stable_record_id(expected),
        "record_version": RECORD_VERSION,
        "record_category": "course_description",
        "course_code": expected,
        "course_scope": {"course_code": expected},
        "term_scope": None,
        "section_scope": None,
        "title": title,
        "description": description,
        "prerequisite_text": prerequisite,
        "exact_source_text": exact_source_text,
        "source": {
            "source_id": "fau-current-catalog",
            "title": "Florida Atlantic University Catalog",
            "publisher": "Florida Atlantic University",
            "url": source_url,
            "locator": {"field": "Course Description", "course_path": f"/courses/{expected}"},
            "catalog_edition": None,
            "effective_scope": None,
        },
        "fetched_at": fetched_at,
        "collection_method": "public_server_rendered_detail_page",
        "raw_evidence_ref": raw_evidence_ref,
        "raw_sha256": raw_sha256 or sha256_text(html_text),
        "content_sha256": sha256_text("\n".join([expected, title, description, prerequisite or ""])),
        "parser_version": PARSER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "unknowns": {
            "catalog_edition": "The current public page does not label a catalog edition.",
            "effective_scope": "No course-level end date or term scope is displayed.",
            "human_verified_at": "Automated collection is not human verification.",
        },
        "limitations": ["Catalog inclusion does not establish current-term availability."],
    }
