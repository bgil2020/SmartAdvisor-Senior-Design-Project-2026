"""Concrete bounded Playwright session using an operator-installed browser."""
from __future__ import annotations

import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


def classify_response_role(url: str, status: int, resource_type: str, document_id: str) -> str:
    lower = url.casefold()
    if any(token in lower for token in ("sentry", "analytics", "telemetry", "google-analytics")):
        return "telemetry"
    same_host = urlparse(url).hostname == "fau.simplesyllabus.com"
    if same_host and resource_type in {"xhr", "fetch"} and (status in {401, 403} or document_id in url):
        return "essential_document"
    return "other"


class PlaywrightSession:
    """One fresh nonpersistent browser context with a single shared deadline."""

    def __init__(self, *, chrome: Path, document_id: str, readiness_text: str, visible: bool, deadline_seconds: float):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Install the optional Python playwright package before browser collection") from exc
        if not chrome.is_file():
            raise RuntimeError("Configured Chrome executable was not found")
        if deadline_seconds <= 0:
            raise ValueError("Browser deadline must be positive")
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(executable_path=str(chrome), headless=not visible)
        self._context = self._browser.new_context()
        self._page = self._context.new_page()
        self._document_id = document_id
        self._readiness_text = readiness_text
        self._deadline_seconds = deadline_seconds
        self._deadline_at: float | None = None
        self._queue: list[dict] = []
        self._cancelled = False
        self._closed = False
        self.last_html = ""
        self.final_url = ""
        self.readiness_visible = False
        self.observed: Counter[tuple[str, int]] = Counter()
        self._page.on("response", self._on_response)

    def _on_response(self, response) -> None:
        role = classify_response_role(response.url, response.status, response.request.resource_type, self._document_id)
        self.observed[(role, response.status)] += 1
        self._queue.append({"kind": "response", "status": response.status, "role": role})

    def navigate(self, url: str) -> None:
        self.final_url = url
        self._deadline_at = time.monotonic() + self._deadline_seconds
        self._page.goto(url, wait_until="commit", timeout=max(1_000, int(self._deadline_seconds * 1_000)))

    def events(self):
        seen = 0
        deadline = self._deadline_at or time.monotonic() + self._deadline_seconds
        while not self._cancelled and time.monotonic() < deadline:
            self._page.wait_for_timeout(100)
            while seen < len(self._queue):
                event = self._queue[seen]
                seen += 1
                yield event
                if self._cancelled:
                    return
            try:
                self.readiness_visible = self._page.get_by_text(self._readiness_text, exact=True).first.is_visible(timeout=100)
            except Exception:
                self.readiness_visible = False
            if self.readiness_visible:
                self.last_html = self._page.content()
                self.final_url = self._page.url
                yield {"kind": "snapshot", "html": self.last_html, "final_url": self.final_url}
                return
        if not self._cancelled:
            self.last_html = self._page.content()
            self.final_url = self._page.url
            yield {"kind": "snapshot", "html": self.last_html, "final_url": self.final_url}

    def cancel(self) -> None:
        self._cancelled = True

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._context.close()
        finally:
            try:
                self._browser.close()
            finally:
                self._pw.stop()
