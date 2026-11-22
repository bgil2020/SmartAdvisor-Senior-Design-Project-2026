"""Offline headed-Chromium smoke: render, cancellation, cleanup, and process RSS."""
from __future__ import annotations

import argparse
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


def browser_launch_options() -> dict[str, object]:
    options: dict[str, object] = {
        "headless": False,
        "args": ["--disable-dev-shm-usage", "--no-sandbox"],
    }
    executable = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE", "").strip()
    if executable:
        if not Path(executable).is_file():
            raise RuntimeError("configured_browser_executable_missing")
        options["executable_path"] = executable
    return options


def verify_application_ui(app_url: str) -> int:
    """Render the bundled Home and navigate through the real Chatbot control."""
    started = time.monotonic()
    peak = family_rss()
    home_rendered = False
    chatbot_navigation = False
    chatbot_rendered = False
    failure_reason = None
    console_errors: list[str] = []
    page_errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(**browser_launch_options())
            try:
                page = browser.new_page()
                page.on("console", lambda message: console_errors.append(message.type) if message.type == "error" else None)
                page.on("pageerror", lambda error: page_errors.append(type(error).__name__))
                try:
                    page.goto(app_url.rstrip("/") + "/", wait_until="networkidle", timeout=15_000)
                    heading = page.get_by_role("heading", name="Welcome to SmartAdvisor")
                    chat_button = page.get_by_role("button", name="Open SmartAdvisor Chat")
                    heading.wait_for(state="visible", timeout=15_000)
                    chat_button.wait_for(state="visible", timeout=15_000)
                    home_rendered = True
                    peak = max(peak, family_rss())
                    chat_button.click(timeout=5_000)
                    page.wait_for_url("**/chatbot", timeout=5_000)
                    chatbot_navigation = page.url.endswith("/chatbot")
                    chat_heading = page.get_by_role("heading", name="SmartAdvisor Chat")
                    chat_heading.wait_for(state="visible", timeout=10_000)
                    chatbot_rendered = True
                    peak = max(peak, family_rss())
                except Exception as error:
                    failure_reason = type(error).__name__
            finally:
                browser.close()
        time.sleep(0.2)
        chromium_left = [
            child.pid
            for child in psutil.Process().children(recursive=True)
            if "chrom" in child.name().casefold()
        ]
        passed = (
            home_rendered
            and chatbot_navigation
            and chatbot_rendered
            and not chromium_left
            and not console_errors
            and not page_errors
        )
        result = {
            "status": "passed" if passed else "failed",
            "failure_reason": failure_reason,
            "home_rendered": home_rendered,
            "chatbot_navigation": chatbot_navigation,
            "chatbot_rendered": chatbot_rendered,
            "console_error_count": len(console_errors),
            "page_error_count": len(page_errors),
            "chromium_children_after_close": chromium_left,
            "peak_family_rss_mb": round(peak / 1024 / 1024, 1),
            "duration_ms": round((time.monotonic() - started) * 1000),
        }
        print(json.dumps(result, sort_keys=True))
        return 0 if passed else 1
    except RuntimeError as error:
        print(json.dumps({"status": "failed", "reason": str(error)}, sort_keys=True))
        return 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-url")
    args = parser.parse_args()
    if os.getenv("ACQUISITION_BROWSER_MODE") != "headed":
        print(json.dumps({"status": "failed", "reason": "headed_mode_not_selected"}))
        return 2
    if args.app_url:
        return verify_application_ui(args.app_url)
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    started = time.monotonic(); peak = family_rss(); timeout_cancelled = False
    try:
        with sync_playwright() as playwright:
            try:
                launch_options = browser_launch_options()
            except RuntimeError as error:
                print(json.dumps({"status": "failed", "reason": str(error)}))
                return 2
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
