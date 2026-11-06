"""Offline extraction from a permitted, complete rendered syllabus document."""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

from backend.course_descriptions.models import SCHEMA_VERSION, normalize_course_code, sha256_text
from .models import PARSER_VERSION, stable_syllabus_id, syllabus_content_hash


class SyllabusParseError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class _RenderedParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.document_depth = 0
        self.has_document = False
        self.all_text: list[str] = []
        self.title_parts: list[str] = []
        self.current_heading_parts: list[str] | None = None
        self.current_body_parts: list[str] = []
        self.sections: list[tuple[str, str]] = []
        self._heading_level: str | None = None
        self.excluded_depth = 0
        self.document_text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        classes = set(attr.get("class", "").lower().split())
        excluded_classes = {"navigation", "sidebar", "footer", "toolbar", "menu", "breadcrumb"}
        if self.document_depth and (tag in {"nav", "footer", "aside", "script", "style", "button"} or attr.get("role") in {"navigation", "menu"} or classes & excluded_classes):
            self.excluded_depth += 1
            return
        if self.excluded_depth:
            self.excluded_depth += 1
            return
        if tag in {"main", "article"} or "data-syllabus-document" in attr:
            self.document_depth += 1
            self.has_document = True
        elif self.document_depth and re.fullmatch(r"h[1-6]", tag):
            if self.current_heading_parts is not None:
                self._finish_section()
            self._heading_level = tag
            self.current_heading_parts = []
        elif self.document_depth and tag in {"p", "li", "br", "div"} and self.current_heading_parts is not None:
            self.current_body_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self.excluded_depth:
            self.excluded_depth -= 1
            return
        if self.document_depth and tag == self._heading_level:
            if tag == "h1" and not self.title_parts:
                self.title_parts = list(self.current_heading_parts or [])
                self.current_heading_parts = None
            self._heading_level = None
        if tag in {"main", "article"} and self.document_depth:
            self._finish_section()
            self.document_depth -= 1

    def handle_data(self, data: str) -> None:
        self.all_text.append(data)
        if not self.document_depth or self.excluded_depth:
            return
        self.document_text_parts.append(data)
        if self._heading_level and self.current_heading_parts is not None:
            self.current_heading_parts.append(data)
        elif self.current_heading_parts is not None:
            self.current_body_parts.append(data)

    def _finish_section(self) -> None:
        if self.current_heading_parts is None:
            return
        heading = re.sub(r"\s+", " ", "".join(self.current_heading_parts)).strip()
        body = "\n".join(line.strip() for line in "".join(self.current_body_parts).splitlines() if line.strip())
        if heading and body and heading != re.sub(r"\s+", " ", "".join(self.title_parts)).strip():
            self.sections.append((heading, body))
        self.current_heading_parts, self.current_body_parts = None, []

    def close(self) -> None:
        super().close()
        self._finish_section()


def classify_page(html: str, final_url: str, http_status: int = 200) -> str:
    parsed = urlparse(final_url)
    parser = _RenderedParser(); parser.feed(html); parser.close()
    text = re.sub(r"\s+", " ", " ".join(parser.all_text)).strip().lower()
    if "login" in parsed.path.lower() or "sign in" in text and len(text) < 2000:
        return "explicit_login_required"
    if re.search(r"automation|automated access|captcha|bot detection", text):
        return "explicit_automation_restriction"
    if http_status in {401, 403}:
        return "generic_access_denied"
    if http_status in {404, 410}:
        return "unpublished_or_missing"
    if "syllabus-library" in parsed.path or not parser.has_document:
        return "javascript_shell_awaiting_render"
    if not parser.title_parts or not parser.sections:
        return "incomplete_extraction"
    return "anonymous_full_document"


def classify_browser_observation(
    html: str,
    final_url: str,
    *,
    failed_requests: list[dict[str, Any]] | None = None,
) -> str:
    """Classify the rendered page; unrelated request failures never override usable content."""
    rendered = classify_page(html, final_url)
    if rendered == "anonymous_full_document":
        return rendered
    failures = failed_requests or []
    essential_denied = any(
        item.get("essential") is True and item.get("status") in {401, 403}
        for item in failures
    )
    if essential_denied:
        return "generic_access_denied"
    return rendered


def parse_rendered_syllabus(
    html: str,
    *,
    course_code: str,
    term_id: str,
    term_name: str,
    section: str,
    source_document_id: str,
    source_url: str,
    fetched_at: str,
    raw_evidence_ref: str,
    instructor: str | None = None,
    render_complete: bool = True,
) -> dict[str, Any]:
    if not render_complete:
        raise SyllabusParseError("incomplete_extraction", "Browser readiness did not establish a complete rendered document")
    if classify_page(html, source_url) != "anonymous_full_document":
        raise SyllabusParseError("incomplete_or_restricted", "Input is not a complete rendered syllabus document")
    parser = _RenderedParser(); parser.feed(html); parser.close()
    if not parser.has_document:
        raise SyllabusParseError("missing_document", "No syllabus document container was found")
    title = re.sub(r"\s+", " ", "".join(parser.title_parts)).strip()
    if not title:
        raise SyllabusParseError("missing_title", "No document title was found")
    code = normalize_course_code(course_code)
    document_visible = " ".join(parser.document_text_parts)
    visible = normalize_course_code(document_visible)
    if code not in visible:
        raise SyllabusParseError("course_identity_mismatch", "Expected course code is absent from the document")
    if normalize_course_code(str(section)) not in visible:
        raise SyllabusParseError("section_identity_mismatch", "Expected section is absent from the document")
    if normalize_course_code(term_name) not in visible and normalize_course_code(term_id) not in visible:
        raise SyllabusParseError("term_identity_mismatch", "Expected term is absent from the document")
    sections = [{"heading": heading, "text": body, "locator": f"heading:{heading}"} for heading, body in parser.sections if heading != title]
    if not sections:
        raise SyllabusParseError("missing_academic_text", "No heading-scoped academic text was found")
    headings = [item["heading"].casefold() for item in sections]
    if len(headings) != len(set(headings)):
        raise SyllabusParseError("ambiguous_academic_text", "Duplicate headings do not provide stable section locators")
    document_text = "\n\n".join(f"{item['heading']}\n{item['text']}" for item in sections)
    record: dict[str, Any] = {
        "record_id": stable_syllabus_id(code, term_id, section, source_document_id),
        "record_version": 1,
        "record_category": "syllabus",
        "course_code": code,
        "course_scope": {"course_code": code},
        "term_scope": {"term_id": term_id, "term_name": term_name},
        "section_scope": {"section": str(section)},
        "title": title,
        "document_version": None,
        "instructor": instructor,
        "document_text": document_text,
        "exact_source_text": document_text,
        "academic_sections": sections,
        "source": {"source_id": source_document_id, "title": title, "publisher": "Florida Atlantic University / Simple Syllabus", "url": source_url, "locator": {"document_id": source_document_id, "section_locators": [item["locator"] for item in sections]}},
        "fetched_at": fetched_at,
        "published_at": None,
        "updated_at": None,
        "observed_access": "anonymous_full_document",
        "collection_method": "offline_parse_of_permitted_rendered_html",
        "raw_evidence_ref": raw_evidence_ref,
        "raw_sha256": sha256_text(html),
        "content_sha256": "",
        "parser_version": PARSER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "unknowns": {"published_at": "Not explicitly stated", "updated_at": "Not explicitly stated"},
        "limitations": ["Parser preserves heading-scoped text and does not infer missing academic sections."],
    }
    record["content_sha256"] = syllabus_content_hash(record)
    return record
