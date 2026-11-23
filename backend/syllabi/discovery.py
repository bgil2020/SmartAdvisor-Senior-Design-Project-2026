"""Bounded discovery of exact FAU Simple Syllabus document identities.

Discovery searches the public, rendered syllabus library.  It never constructs a
document ID, calls a private API, or treats a fuzzy course-name result as an
approved source.  The first result is selected only after exact course, term,
and section filtering; the normal document parser validates that identity again.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, unquote, urljoin, urlparse, urlunparse

from backend.course_descriptions.models import normalize_course_code
from .playwright_driver import resolve_browser_executable

LIBRARY_URL = "https://fau.simplesyllabus.com/en-US/syllabus-library"
ALLOWED_HOST = "fau.simplesyllabus.com"
_TERM_SEASONS = {"01": "Spring", "05": "Summer", "08": "Fall"}


class _DocumentLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text)))
            self._href = None
            self._text = []


def term_name_from_id(term_id: str) -> str | None:
    match = re.fullmatch(r"(\d{4})(01|05|08)", str(term_id).strip())
    return f"{_TERM_SEASONS[match.group(2)]} {match.group(1)}" if match else None


def _canonical_document_url(href: str, *, base_url: str = LIBRARY_URL) -> tuple[str, str, str] | None:
    absolute = urljoin(base_url, href)
    parsed = urlparse(absolute)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST:
        return None
    match = re.fullmatch(r"/(?:en-US/)?doc/([A-Za-z0-9_-]+)/([^/]+)", parsed.path)
    if not match:
        return None
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["mode"] = "view"
    canonical = urlunparse(("https", ALLOWED_HOST, parsed.path, "", urlencode(query), ""))
    return canonical, match.group(1), unquote(match.group(2))


def _identity_matches(slug_and_text: str, *, course_code: str, term_id: str, section: str) -> bool:
    course = normalize_course_code(course_code)
    term_name = term_name_from_id(term_id)
    section_value = str(section).strip().upper()
    if not course or not term_name or not section_value:
        return False
    course_parts = re.fullmatch(r"([A-Z]+)(\d+[A-Z]*)", course)
    if not course_parts:
        return False
    visible = re.sub(r"[^A-Z0-9]+", " ", slug_and_text.upper())
    exact_course = re.search(
        rf"(?:^|\s){re.escape(course_parts.group(1))}\s*{re.escape(course_parts.group(2))}(?:\s|$)",
        visible,
    )
    if not exact_course or normalize_course_code(term_name) not in normalize_course_code(visible):
        return False
    # Section must be a distinct token rather than an arbitrary number inside a
    # course title or document ID.
    return bool(re.search(rf"(?:^|\s){re.escape(section_value)}(?:\s|$)", visible))


def exact_syllabus_candidates(
    html: str,
    *,
    course_code: str,
    term_id: str,
    section: str,
    base_url: str = LIBRARY_URL,
) -> list[dict[str, Any]]:
    """Return rendered document links matching all requested identity fields."""
    parser = _DocumentLinkParser()
    parser.feed(html)
    parser.close()
    matches: list[dict[str, Any]] = []
    seen: set[str] = set()
    for href, anchor_text in parser.links:
        parsed = _canonical_document_url(href, base_url=base_url)
        if not parsed:
            continue
        view_url, document_id, slug = parsed
        if view_url in seen or not _identity_matches(
            f"{slug} {anchor_text}",
            course_code=course_code,
            term_id=term_id,
            section=section,
        ):
            continue
        seen.add(view_url)
        matches.append({
            "course_code": normalize_course_code(course_code),
            "term_id": str(term_id),
            "term_name": term_name_from_id(str(term_id)),
            "section": str(section),
            "source_document_id": document_id,
            "view_url": view_url,
            "discovered_from": base_url,
        })
    return matches


@dataclass(frozen=True)
class DiscoveryLimits:
    timeout_seconds: float = 20.0
    total_response_budget: int = 60
    max_rendered_html_bytes: int = 2 * 1024 * 1024

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0 or self.total_response_budget < 1 or self.max_rendered_html_bytes < 1024:
            raise ValueError("Discovery limits must be positive")


class PlaywrightDiscoverySession:
    """Fresh browser context that uses only the public library's visible UI."""

    def __init__(self, *, visible: bool, limits: DiscoveryLimits):
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        try:
            resolved = resolve_browser_executable(self._pw.chromium.executable_path)
            self._browser = self._pw.chromium.launch(executable_path=str(resolved.path), headless=not visible)
        except BaseException:
            self._pw.stop()
            raise
        self._context = self._browser.new_context()
        self._page = self._context.new_page()
        self._limits = limits
        self._responses = 0
        self._denied = False
        self._response_budget_exhausted = False
        self._page.on("response", self._on_response)

    def _on_response(self, response) -> None:
        self._responses += 1
        if urlparse(response.url).hostname == ALLOWED_HOST and response.status in {401, 403, 429}:
            self._denied = True
        if self._responses >= self._limits.total_response_budget:
            self._response_budget_exhausted = True
        if self._denied or self._response_budget_exhausted:
            try:
                self._page.evaluate("window.stop()")
            except Exception:
                pass

    def search(self, query: str) -> dict[str, Any]:
        timeout_ms = max(1_000, int(self._limits.timeout_seconds * 1_000))
        started = time.monotonic()
        self._page.goto(LIBRARY_URL, wait_until="domcontentloaded", timeout=timeout_ms)
        search = self._page.get_by_placeholder(re.compile(r"looking for something", re.I)).first
        search.fill(query, timeout=timeout_ms)
        search.press("Enter", timeout=timeout_ms)
        self._page.wait_for_timeout(min(2_000, timeout_ms))
        html = self._page.content()
        rendered_bytes = len(html.encode("utf-8"))
        if self._denied:
            status = "source_access_denied"
        elif self._response_budget_exhausted:
            status = "discovery_response_budget_exhausted"
        elif rendered_bytes > self._limits.max_rendered_html_bytes:
            status = "discovery_response_too_large"
        else:
            status = "rendered"
        return {
            "status": status,
            "html": html if status == "rendered" else "",
            "actual_observed_responses": self._responses,
            "rendered_html_bytes": rendered_bytes,
            "logical_navigations": 1,
            "duration_ms": round((time.monotonic() - started) * 1000),
        }

    def close(self) -> None:
        try:
            self._context.close()
        finally:
            try:
                self._browser.close()
            finally:
                self._pw.stop()


def discover_exact_syllabus(
    course_code: str,
    term_id: str,
    section: str,
    *,
    session_factory: Callable[..., Any] = PlaywrightDiscoverySession,
) -> dict[str, Any]:
    """Find and select the first rendered result with exact requested identity."""
    if os.getenv("SYLLABUS_AUTO_DISCOVERY_ENABLED", "false").casefold() != "true":
        return {"status": "disabled", "mapping": None, "logical_navigations": 0}
    term_name = term_name_from_id(str(term_id))
    if term_name is None:
        return {"status": "unsupported_term", "mapping": None, "logical_navigations": 0}
    limits = DiscoveryLimits(
        timeout_seconds=max(1.0, float(os.getenv("SYLLABUS_DISCOVERY_TIMEOUT_SECONDS", "20"))),
        total_response_budget=max(1, int(os.getenv("SYLLABUS_DISCOVERY_MAX_RESPONSES", "60"))),
        max_rendered_html_bytes=max(1024, int(os.getenv("SYLLABUS_DISCOVERY_MAX_RENDERED_HTML_BYTES", str(2 * 1024 * 1024)))),
    )
    session = session_factory(visible=True, limits=limits)
    try:
        result = session.search(f"{normalize_course_code(course_code)} {str(section).strip()}")
    except Exception as exc:
        return {"status": "discovery_error", "mapping": None, "logical_navigations": 1, "error_type": type(exc).__name__}
    finally:
        session.close()
    diagnostics = {key: value for key, value in result.items() if key != "html"}
    if result.get("status") != "rendered":
        return {**diagnostics, "mapping": None}
    candidates = exact_syllabus_candidates(
        str(result.get("html", "")),
        course_code=course_code,
        term_id=str(term_id),
        section=str(section),
    )
    if not candidates:
        return {**diagnostics, "status": "no_exact_source_match", "mapping": None, "exact_match_count": 0}
    return {
        **diagnostics,
        "status": "exact_source_selected",
        "mapping": candidates[0],
        "exact_match_count": len(candidates),
        "selection_strategy": "first_exact_course_term_section_match",
    }
