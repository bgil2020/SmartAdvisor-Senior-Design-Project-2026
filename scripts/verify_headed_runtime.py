"""Offline headed-Chromium smoke: render, cancellation, cleanup, and process RSS."""
from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import psutil
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/synthetic.html":
            body = b"<!doctype html><main data-smoke-ready><h1>Synthetic syllabus</h1><p>Rendered locally.</p></main>"
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        elif self.path == "/slow":
            time.sleep(2)
            body = b"slow"
            self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()

    def log_message(self, *_args: object) -> None:
        return


def family_rss() -> int:
    process = psutil.Process()
    family = [process, *process.children(recursive=True)]
    return sum(item.memory_info().rss for item in family if item.is_running())


def main() -> int:
    if os.getenv("ACQUISITION_BROWSER_MODE") != "headed":
        print(json.dumps({"status": "failed", "reason": "headed_mode_not_selected"}))
        return 2
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    started = time.monotonic(); peak = family_rss(); timeout_cancelled = False
    try:
        with sync_playwright() as playwright:
            launch_options = {"headless": False, "args": ["--disable-dev-shm-usage", "--no-sandbox"]}
            executable = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE", "").strip()
            if executable:
                if not Path(executable).is_file():
                    print(json.dumps({"status": "failed", "reason": "configured_browser_executable_missing"}))
                    return 2
                launch_options["executable_path"] = executable
            browser = playwright.chromium.launch(**launch_options)
            try:
                page = browser.new_page()
                page.goto("http://127.0.0.1:8765/synthetic.html", wait_until="domcontentloaded", timeout=5_000)
                rendered = page.locator("[data-smoke-ready]").count() == 1 and "Rendered locally" in page.locator("main").inner_text()
                peak = max(peak, family_rss())
                try:
                    page.goto("http://127.0.0.1:8765/slow", timeout=100)
                except PlaywrightTimeoutError:
                    timeout_cancelled = True
                peak = max(peak, family_rss())
            finally:
                browser.close()
        time.sleep(0.2)
        chromium_left = [child.pid for child in psutil.Process().children(recursive=True) if "chrom" in child.name().casefold()]
        result = {
            "status": "passed" if rendered and timeout_cancelled and not chromium_left else "failed",
            "rendered": rendered,
            "timeout_cancelled": timeout_cancelled,
            "chromium_children_after_close": chromium_left,
            "peak_family_rss_mb": round(peak / 1024 / 1024, 1),
            "duration_ms": round((time.monotonic() - started) * 1000),
        }
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "passed" else 1
    finally:
        server.shutdown(); server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
