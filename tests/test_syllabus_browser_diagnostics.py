"""Offline tests for sanitized syllabus browser diagnostics and route guards."""
from __future__ import annotations

import json
from types import SimpleNamespace

from backend.syllabi.browser_diagnostics import (
    SanitizedBrowserDiagnostics,
    approved_document_path,
    classify_response_details,
    request_ownership,
    sanitize_error_summary,
    sanitize_url,
)
from scripts.syllabus_browser_collect import PlaywrightSession

DOCUMENT_ID = "a4bh2nqsq"
EXPECTED_URL = f"https://fau.simplesyllabus.com/doc/{DOCUMENT_ID}/Fall-2026-EEL-3111-001?mode=view"


class FakeRequest:
    def __init__(self, url=EXPECTED_URL, *, method="GET", resource_type="document", navigation=True, frame=None, frame_error=False, service_worker=None, redirected_from=None, failure=None):
        self.url = url
        self.method = method
        self.resource_type = resource_type
        self._navigation = navigation
        self._frame = frame
        self._frame_error = frame_error
        self.service_worker = service_worker
        self.redirected_from = redirected_from
        self.failure = failure

    @property
    def frame(self):
        if self._frame_error:
            raise RuntimeError("frame is unavailable")
        return self._frame

    def is_navigation_request(self):
        return self._navigation


class FakeResponse:
    def __init__(self, request, status, content_type="text/html", from_service_worker=False):
        self.request = request
        self.status = status
        self._content_type = content_type
        self.from_service_worker = from_service_worker

    def header_value(self, name):
        return self._content_type if name == "content-type" else None


class FakeRoute:
    def __init__(self, *, fail_continue=False):
        self.continued = 0
        self.aborted = 0
        self.fail_continue = fail_continue

    def continue_(self):
        self.continued += 1
        if self.fail_continue:
            raise RuntimeError("route continue failed")

    def abort(self):
        self.aborted += 1


def diagnostics(tmp_path):
    return SanitizedBrowserDiagnostics(
        destination=tmp_path / "diagnostic.json",
        diagnostic_id="fixture-diagnostic",
        document_id=DOCUMENT_ID,
        expected_url=EXPECTED_URL,
        launch={"headless": True, "environment_capture": "none"},
        now=lambda: "2026-11-06T12:00:00+00:00",
    )


def test_url_and_error_diagnostics_redact_values_credentials_and_local_paths():
    secret_url = "https://fau.simplesyllabus.com/api2/private-value?token=do-not-keep&mode=view#fragment"
    sanitized = sanitize_url(secret_url, document_id=DOCUMENT_ID, expected_url=EXPECTED_URL)
    rendered = json.dumps(sanitized)
    assert sanitized["approved_host"] is True
    assert sanitized["query_keys"] == ["mode", "token"]
    assert "private-value" not in rendered
    assert "do-not-keep" not in rendered
    assert "fragment" not in rendered
    summary = sanitize_error_summary("failed https://example.test/x?token=secret for person@example.test at C:\\Users\\person\\file")
    assert "secret" not in summary and "person@example" not in summary and "C:\\Users" not in summary


def test_redirect_relationship_ownership_and_duplicate_response_are_recorded_once(tmp_path):
    main_frame = object()
    first = FakeRequest(frame=main_frame)
    redirected = FakeRequest(
        f"https://fau.simplesyllabus.com/en-US/doc/{DOCUMENT_ID}/Fall-2026-EEL-3111-001?mode=view",
        frame=main_frame,
        redirected_from=first,
    )
    recorder = diagnostics(tmp_path)
    recorder.record_response(FakeResponse(first, 302), main_frame=main_frame)
    final_response = FakeResponse(redirected, 200)
    recorder.record_response(final_response, main_frame=main_frame)
    assert recorder.record_response(final_response, main_frame=main_frame) is None
    assert recorder.record_response(FakeResponse(redirected, 200), main_frame=main_frame) is None
    recorder.write()
    payload = json.loads((tmp_path / "diagnostic.json").read_text(encoding="utf-8"))
    responses = [item for item in payload["events"] if item["kind"] == "response"]
    assert len(responses) == 2
    assert responses[1]["redirected_from_request_id"] == responses[0]["request_id"]
    assert responses[1]["endpoint"]["expected_document_path"] is True
    assert approved_document_path(f"/en-US/doc/{DOCUMENT_ID}/name", DOCUMENT_ID)


def test_service_worker_and_preframe_requests_never_require_frame_access():
    main_frame = object()
    service_worker_request = FakeRequest(frame_error=True, service_worker=object(), navigation=False)
    preframe_navigation = FakeRequest(frame_error=True, navigation=True)
    assert request_ownership(service_worker_request, main_frame=main_frame) == "service_worker"
    assert request_ownership(preframe_navigation, main_frame=main_frame) == "navigation_without_frame"


def test_route_handler_completes_or_aborts_and_records_actions(tmp_path):
    main_frame = object()
    recorder = diagnostics(tmp_path)
    session = SimpleNamespace(
        _page=SimpleNamespace(main_frame=main_frame),
        _document_id=DOCUMENT_ID,
        _queue=[],
        _diagnostics=recorder,
    )
    allowed = FakeRoute()
    PlaywrightSession._route_request(session, allowed, FakeRequest(frame_error=True))
    assert allowed.continued == 1 and allowed.aborted == 0

    blocked = FakeRoute()
    PlaywrightSession._route_request(
        session,
        blocked,
        FakeRequest("https://example.test/elsewhere", frame=main_frame),
    )
    assert blocked.aborted == 1

    broken = FakeRoute(fail_continue=True)
    PlaywrightSession._route_request(session, broken, FakeRequest(frame=main_frame))
    assert broken.continued == 1 and broken.aborted == 1
    assert recorder.events[-1]["route_action"] == "abort_after_handler_error"
    assert recorder.events[-1]["route_completed"] is True


def test_classification_reasons_preserve_denial_and_exclude_telemetry():
    role, reason = classify_response_details(
        "https://fau.simplesyllabus.com/api/bootstrap", 403, "xhr", DOCUMENT_ID
    )
    assert (role, reason) == (
        "essential_document",
        "approved_host_auth_denial_on_document_capable_request",
    )
    assert classify_response_details("https://sentry.io/store", 403, "fetch", DOCUMENT_ID)[0] == "telemetry"
    assert classify_response_details("https://fau.simplesyllabus.com/assets/app.js", 403, "script", DOCUMENT_ID)[0] == "other"


def test_request_failure_is_sanitized_and_diagnostic_write_is_idempotent(tmp_path):
    recorder = diagnostics(tmp_path)
    request = FakeRequest(
        "https://fau.simplesyllabus.com/api/private-value?signature=sensitive",
        navigation=False,
        resource_type="fetch",
        frame=object(),
        failure="net::ERR_FAILED https://example.test/?token=sensitive",
    )
    recorder.record_request_failure(request, main_frame=object())
    recorder.write()
    recorder.write()
    rendered = (tmp_path / "diagnostic.json").read_text(encoding="utf-8")
    assert "private-value" not in rendered
    assert "sensitive" not in rendered
    assert "ERR_FAILED" in rendered
