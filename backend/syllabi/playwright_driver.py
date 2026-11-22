"""Concrete bounded Playwright session using an operator-installed browser."""
from __future__ import annotations

import os
import platform
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse


WINDOWS_CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


class BrowserExecutableConfigurationError(RuntimeError):
    """Safe, operator-actionable browser configuration failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ResolvedBrowserExecutable:
    path: Path
    source: str


def resolve_browser_executable(
    playwright_executable: str | Path,
    *,
    explicit_path: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    platform_name: str | None = None,
) -> ResolvedBrowserExecutable:
    """Resolve and validate the acquisition browser without silent fallback.

    Precedence is an explicit factory argument, ``ACQUISITION_CHROME_PATH``,
    the intentional local Windows Chrome default, then Playwright's supported
    bundled Chromium discovery on other platforms.
    """
    environment = os.environ if environ is None else environ
    configured = str(explicit_path).strip() if explicit_path is not None else environment.get("ACQUISITION_CHROME_PATH", "").strip()
    system = platform.system() if platform_name is None else platform_name
    if configured:
        candidate, source, code = Path(configured), "explicit", "explicit_browser_executable_invalid"
    elif system == "Windows":
        candidate, source, code = WINDOWS_CHROME, "windows_default", "windows_browser_executable_invalid"
    else:
        candidate, source, code = Path(playwright_executable), "playwright", "playwright_browser_executable_invalid"
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise BrowserExecutableConfigurationError(code, f"Acquisition browser executable is invalid ({source}).")
    return ResolvedBrowserExecutable(path=candidate, source=source)


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

    def __init__(self, *, chrome: Path | None = None, document_id: str, readiness_text: str, visible: bool, deadline_seconds: float):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Install the optional Python playwright package before browser collection") from exc
        if deadline_seconds <= 0:
            raise ValueError("Browser deadline must be positive")
        self._pw = sync_playwright().start()
        try:
            resolved = resolve_browser_executable(self._pw.chromium.executable_path, explicit_path=chrome)
            self.browser_executable_source = resolved.source
            self._browser = self._pw.chromium.launch(executable_path=str(resolved.path), headless=not visible)
        except BaseException:
            self._pw.stop()
            raise
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
