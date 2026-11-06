"""Manual one-document Playwright collection for tracked syllabus identities.

Adapted from the peer's visible-browser prototype. This command performs one
anonymous navigation and writes ignored raw HTML only after the existing browser
guard classifies a complete rendered document. Parsing and acceptance remain in
``scripts/syllabi.py``.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.course_descriptions.models import read_json
from backend.syllabi.browser_probe import BrowserProbeLimits, probe_browser_session
from backend.syllabi.browser_diagnostics import (
    SanitizedBrowserDiagnostics,
    approved_document_path,
    classify_response_details,
    request_ownership,
)

MANIFEST = ROOT / "data" / "syllabi" / "sample-manifest.json"
RAW = ROOT / "data" / "syllabi" / "raw"
DEFAULT_CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def classify_response_role(url: str, status: int, resource_type: str, document_id: str) -> str:
    return classify_response_details(url, status, resource_type, document_id)[0]


class PlaywrightSession:
    def __init__(self, *, chrome: Path, document_id: str, expected_url: str, readiness_text: str, visible: bool, deadline_seconds: float, diagnostics_path: Path, diagnostic_id: str):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Install the optional Python playwright package before manual browser collection") from exc
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(executable_path=str(chrome), headless=not visible)
        self._context = self._browser.new_context(
            accept_downloads=False,
            service_workers="block",
        )
        self._page = self._context.new_page()
        self._document_id = document_id
        self._readiness_text = readiness_text
        self._deadline_seconds = deadline_seconds
        self._queue: list[dict] = []
        self._cancelled = False
        self._closed = False
        self.last_html = ""
        self.final_url = ""
        self.readiness_visible = False
        self.observed: Counter[tuple[str, int]] = Counter()
        self._diagnostics = SanitizedBrowserDiagnostics(
            destination=diagnostics_path,
            diagnostic_id=diagnostic_id,
            document_id=document_id,
            expected_url=expected_url,
            launch={
                "browser": "configured_installed_chrome",
                "browser_version": self._browser.version,
                "headless": not visible,
                "nonpersistent_context": True,
                "service_workers": "block",
                "accept_downloads": False,
                "working_directory": "repository_root",
                "environment_capture": "none",
            },
        )
        self._context.on("response", self._on_response)
        self._context.on("requestfailed", self._on_request_failed)
        self._page.on("pageerror", lambda error: self._diagnostics.record_browser_error("page_error", error))
        self._page.on("crash", lambda *_: self._diagnostics.record_browser_error("page_crash", "page crashed"))
        self._page.route("**/*", self._route_request)

    def _route_request(self, route, request) -> None:
        action = "continue"
        error = None
        completed = False
        try:
            if request.is_navigation_request():
                owner = request_ownership(request, main_frame=self._page.main_frame)
                parsed = urlparse(request.url)
                constrained = owner in {"main_frame", "navigation_without_frame"}
                if constrained and (parsed.scheme != "https" or parsed.hostname != "fau.simplesyllabus.com" or not approved_document_path(parsed.path, self._document_id)):
                    action = "abort"
                    self._queue.append({"kind": "error", "error": "blocked navigation outside the exact verified syllabus mapping"})
            if action == "abort":
                route.abort()
            else:
                route.continue_()
            completed = True
        except Exception as exc:
            error = exc
            self._queue.append({"kind": "error", "error": f"browser route handler failed ({type(exc).__name__})"})
            if not completed and action != "abort":
                action = "abort_after_handler_error"
                try:
                    route.abort()
                    completed = True
                except Exception:
                    completed = False
        finally:
            self._diagnostics.record_route(
                request,
                main_frame=self._page.main_frame,
                action=action,
                completed=completed,
                error=type(error).__name__ if error else None,
            )

    def _on_response(self, response) -> None:
        event = self._diagnostics.record_response(response, main_frame=self._page.main_frame)
        if event is None:
            return
        self.observed[(event["role"], event["status"])] += 1
        self._queue.append({"kind": "response", "status": event["status"], "role": event["role"]})

    def _on_request_failed(self, request) -> None:
        self._diagnostics.record_request_failure(request, main_frame=self._page.main_frame)

    def navigate(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "fau.simplesyllabus.com" or not approved_document_path(parsed.path, self._document_id):
            raise RuntimeError("Refusing browser navigation outside the exact verified syllabus mapping")
        self.final_url = url
        self._page.goto(url, wait_until="commit", timeout=min(15000, int(self._deadline_seconds * 1000)))

    def events(self):
        seen = 0
        deadline = time.monotonic() + self._deadline_seconds
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
                parsed = urlparse(self.final_url)
                if parsed.hostname != "fau.simplesyllabus.com" or not approved_document_path(parsed.path, self._document_id):
                    yield {"kind": "error", "error": "final browser URL left the exact verified syllabus mapping"}
                    return
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
                try:
                    self._pw.stop()
                finally:
                    self._diagnostics.write()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document-id", required=True, help="Document ID already present in data/syllabi/sample-manifest.json")
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--chrome", type=Path, default=DEFAULT_CHROME)
    parser.add_argument("--raw-root", type=Path, default=RAW, help="Ignored local raw-evidence root")
    parser.add_argument("--diagnostics-root", type=Path, default=ROOT / "data" / "syllabi" / "diagnostics", help="Ignored sanitized request-diagnostics root")
    parser.add_argument("--readiness-text", default="Course Evaluation Method")
    parser.add_argument("--deadline-seconds", type=float, default=20.0)
    parser.add_argument("--visible", action="store_true")
    args = parser.parse_args()
    documents = read_json(MANIFEST)["documents"]
    matches = [item for item in documents if item["source_document_id"] == args.document_id]
    if len(matches) != 1:
        parser.error("document ID must identify exactly one tracked manifest entry")
    if not args.chrome.is_file():
        parser.error("Chrome executable was not found; no browser runtime is downloaded automatically")
    item = matches[0]
    diagnostic_id = args.batch_id
    session = PlaywrightSession(
        chrome=args.chrome,
        document_id=args.document_id,
        expected_url=item["view_url"],
        readiness_text=args.readiness_text,
        visible=args.visible,
        deadline_seconds=args.deadline_seconds,
        diagnostics_path=args.diagnostics_root / f"{diagnostic_id}.json",
        diagnostic_id=diagnostic_id,
    )
    result = probe_browser_session(session, item["view_url"], limits=BrowserProbeLimits())
    saved = None
    if result["status"] == "anonymous_full_document" and session.last_html:
        destination = args.raw_root / args.batch_id / f"{args.document_id}.html"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(session.last_html, encoding="utf-8")
        try:
            saved = destination.resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            saved = destination.resolve().as_posix()
    output = {
        "document": {key: item[key] for key in ("course_code", "term_id", "term_name", "section", "source_document_id", "view_url")},
        "probe": result,
        "final_url": session.final_url,
        "readiness_visible": session.readiness_visible,
        "saved_raw_evidence": saved,
        "diagnostic_id": diagnostic_id,
        "diagnostic_ref": f"diagnostics/{diagnostic_id}.json",
        "response_counts": [
            {"role": role, "status": status, "count": count}
            for (role, status), count in sorted(session.observed.items())
        ],
    }
    print(json.dumps(output, indent=2))
    return 0 if saved else 2


if __name__ == "__main__":
    raise SystemExit(main())
