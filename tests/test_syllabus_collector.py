from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import httpx
import pytest

from backend.course_descriptions.http import FetchConfig
from backend.course_descriptions.models import SCHEMA_VERSION, read_json, write_json
from backend.course_descriptions.storage import compare_batches
from backend.syllabi.models import syllabus_content_hash
from backend.syllabi.browser_probe import BrowserProbeLimits, probe_browser_session
from backend.syllabi.parser import SyllabusParseError, classify_browser_observation, classify_page, parse_rendered_syllabus
from backend.syllabi.playwright_driver import BrowserExecutableConfigurationError, resolve_browser_executable
from backend.syllabi.probe import probe_documents
from backend.syllabi.storage import accept_batch, rollback_accepted, validate_batch, validate_record
from scripts.syllabus_browser_collect import classify_response_role

FIXTURES = Path(__file__).parent / "syllabi" / "fixtures"


def test_linux_acquisition_uses_playwright_managed_browser(tmp_path):
    executable = tmp_path / "chromium"
    executable.write_bytes(b"browser")
    executable.chmod(0o755)

    resolved = resolve_browser_executable(executable, environ={}, platform_name="Linux")

    assert resolved.path == executable
    assert resolved.source == "playwright"


def test_windows_acquisition_preserves_local_chrome_default(tmp_path, monkeypatch):
    from backend.syllabi import playwright_driver

    executable = tmp_path / "chrome.exe"
    executable.write_bytes(b"browser")
    executable.chmod(0o755)
    monkeypatch.setattr(playwright_driver, "WINDOWS_CHROME", executable)

    resolved = resolve_browser_executable(tmp_path / "unused", environ={}, platform_name="Windows")

    assert resolved.path == executable
    assert resolved.source == "windows_default"


def test_explicit_acquisition_browser_override_has_precedence(tmp_path):
    explicit = tmp_path / "operator-browser"
    bundled = tmp_path / "playwright-browser"
    explicit.write_bytes(b"browser")
    explicit.chmod(0o755)

    resolved = resolve_browser_executable(
        bundled,
        environ={"ACQUISITION_CHROME_PATH": str(explicit)},
        platform_name="Linux",
    )

    assert resolved.path == explicit
    assert resolved.source == "explicit"


def test_invalid_explicit_acquisition_browser_never_falls_back(tmp_path):
    bundled = tmp_path / "playwright-browser"
    bundled.write_bytes(b"browser")
    bundled.chmod(0o755)

    with pytest.raises(BrowserExecutableConfigurationError) as caught:
        resolve_browser_executable(
            bundled,
            environ={"ACQUISITION_CHROME_PATH": str(tmp_path / "missing")},
            platform_name="Linux",
        )

    assert caught.value.code == "explicit_browser_executable_invalid"


class FakeBrowserSession:
    def __init__(self, events):
        self._events = events
        self.navigated = []
        self.cancelled = False
        self.closed = False

    def navigate(self, url): self.navigated.append(url)
    def events(self): return iter(self._events)
    def cancel(self): self.cancelled = True
    def close(self): self.closed = True


class FakeRuntimeSession:
    def __init__(self, html: str, final_url: str):
        self.last_html = html
        self.final_url = final_url


def full_document_probe() -> dict:
    return {
        "status": "anonymous_full_document",
        "stop_reason": "rendered_document_ready",
        "logical_navigations": 1,
        "actual_observed_responses": 7,
        "essential_document_requests": 1,
        "essential_document_failures": 0,
        "telemetry_responses": 1,
        "access_denials": 0,
        "cancelled": False,
        "limits": {
            "essential_failure_budget": 2,
            "access_denial_threshold": 1,
            "total_response_budget": 60,
            "max_rendered_html_bytes": 2 * 1024 * 1024,
        },
    }


def runtime_mapping(course_code: str = "COP4331") -> dict:
    return {
        "course_code": course_code,
        "term_id": "202608",
        "term_name": "Fall 2026 1 Full Term",
        "section": "002",
        "instructor": "Ionut Cardei",
        "source_document_id": "sb4d8l8wb",
        "view_url": "https://fau.simplesyllabus.com/doc/sb4d8l8wb/Fall-2026-COP-4331-002?mode=view",
    }


def record(section="002", source_id="sb4d8l8wb"):
    html = (FIXTURES / "rendered_complete.html").read_text(encoding="utf-8").replace("4331-002", f"4331-{section}")
    return parse_rendered_syllabus(html, course_code="COP4331", term_id="202608", term_name="Fall 2026 1 Full Term", section=section, source_document_id=source_id, source_url=f"https://fau.simplesyllabus.com/doc/{source_id}/COP-4331?mode=view", fetched_at="2026-10-30T12:00:00Z", raw_evidence_ref="tests/syllabi/fixtures/rendered_complete.html", instructor="Ionut Cardei")


def batch(batch_id, records, outcomes=None):
    return {"schema_version": SCHEMA_VERSION, "batch_id": batch_id, "delivery_mode": "partial", "created_at": "2026-10-30T12:00:00Z", "source_manifest": "data/syllabi/sample-manifest.json", "records": records, "outcomes": outcomes or [], "limitations": ["partial"]}


def accepted(records, batch_id="syllabi-empty"):
    return {"schema_version": SCHEMA_VERSION, "dataset_id": "smartadvisor-syllabi", "accepted_batch_id": batch_id, "accepted_at": None, "previous_accepted_batch_id": None, "records": records}


def test_extracts_complete_document_identity_sections_and_locators():
    item = record()
    assert item["course_code"] == "COP4331"
    assert item["term_scope"] == {"term_id": "202608", "term_name": "Fall 2026 1 Full Term"}
    assert item["section_scope"] == {"section": "002"}
    assert [section["heading"] for section in item["academic_sections"]] == ["Course Description", "Learning Outcomes", "Assessments and Grading"]
    assert all(section["locator"].startswith("heading:") for section in item["academic_sections"])
    assert "Logout" not in item["document_text"]
    assert "Section navigation" not in item["document_text"]
    assert "Privacy Terms Support" not in item["document_text"]
    assert validate_batch(batch("parsed-one", [item]))["valid"] is True


def test_parser_preserves_grading_table_cell_and_row_boundaries():
    html = """
    <main data-syllabus-document>
      <h1>CAP 4773-001 Fall 2026</h1>
      <h2>Course Grading Scale</h2>
      <table>
        <tr><th>Grade</th><th>Range</th></tr>
        <tr><td>A</td><td>90.0% - 100.00%</td></tr>
        <tr><td>B+</td><td>87% - 89%</td></tr>
      </table>
    </main>
    """
    parsed = parse_rendered_syllabus(
        html,
        course_code="CAP4773",
        term_id="202608",
        term_name="Fall 2026",
        section="001",
        source_document_id="table-fixture",
        source_url="https://example.test/doc/table-fixture",
        fetched_at="2026-11-20T00:00:00Z",
        raw_evidence_ref="synthetic-table-fixture",
    )
    scale = parsed["academic_sections"][0]["text"]

    assert "Grade\tRange" in scale
    assert "A\t90.0% - 100.00%" in scale
    assert "B+\t87% - 89%" in scale
    assert "A90.0%" not in scale


def test_rejects_library_shell_login_redirect_and_missing_or_ambiguous_text():
    shell = (FIXTURES / "library_shell.html").read_text(encoding="utf-8")
    assert classify_page(shell, "https://fau.simplesyllabus.com/en-US/syllabus-library") == "javascript_shell_awaiting_render"
    assert classify_page("<p>Sign in</p>", "https://fau.simplesyllabus.com/login") == "explicit_login_required"
    assert classify_page("", "https://fau.simplesyllabus.com/doc/x/name", 403) == "generic_access_denied"
    assert classify_page("<main><h1>COP 4331-002</h1></main>", "https://fau.simplesyllabus.com/doc/x/name") == "incomplete_extraction"
    assert classify_page("<p>Automated access is not allowed.</p>", "https://fau.simplesyllabus.com/doc/x/name") == "explicit_automation_restriction"
    with pytest.raises(SyllabusParseError):
        parse_rendered_syllabus("<main><h1>COP 4331</h1></main>", course_code="COP4331", term_id="202608", term_name="Fall", section="002", source_document_id="x", source_url="https://fau.simplesyllabus.com/doc/x/name", fetched_at="x", raw_evidence_ref="x")
    duplicate = "<main><h1>COP 4331-002</h1><p>Fall 2026</p><h2>Topics</h2><p>One</p><h2>Topics</h2><p>Two</p></main>"
    with pytest.raises(SyllabusParseError) as caught:
        parse_rendered_syllabus(duplicate, course_code="COP4331", term_id="202608", term_name="Fall", section="002", source_document_id="x", source_url="https://fau.simplesyllabus.com/doc/x/name", fetched_at="x", raw_evidence_ref="x")
    assert caught.value.code == "ambiguous_academic_text"


def test_direct_manifest_link_readiness_and_unrelated_failure_do_not_override_rendered_success():
    html = (FIXTURES / "rendered_complete.html").read_text(encoding="utf-8")
    exact_url = "https://fau.simplesyllabus.com/doc/sb4d8l8wb/Fall-2026-1-Full-Term-COP-4331-002-Object-Oriented-Design-%26-Prog?mode=view"
    failures = [{"status": 429, "url": "https://sentry.io/store", "essential": False}, {"status": 403, "url": "https://example.invalid/optional", "essential": False}]
    assert classify_browser_observation(html, exact_url, failed_requests=failures) == "anonymous_full_document"
    with pytest.raises(SyllabusParseError) as caught:
        parse_rendered_syllabus(html, course_code="COP4331", term_id="202608", term_name="Fall 2026 1 Full Term", section="002", source_document_id="sb4d8l8wb", source_url=exact_url, fetched_at="x", raw_evidence_ref="x", render_complete=False)
    assert caught.value.code == "incomplete_extraction"


def test_empty_shell_with_essential_403_is_generic_denial_not_login_requirement():
    shell = (FIXTURES / "library_shell.html").read_text(encoding="utf-8")
    exact_url = "https://fau.simplesyllabus.com/doc/a4bh2nqsq/Fall-2026-1-Full-Term-EEL-3111-001-Circuits-1?mode=view"
    failures = [{"status": 403, "url": "browser-generated-document-request", "essential": True}]
    assert classify_browser_observation(shell, exact_url, failed_requests=failures) == "generic_access_denied"


def test_localized_document_redirect_preserves_exact_source_identity():
    parsed = record()
    parsed["source"]["url"] = "https://fau.simplesyllabus.com/en-US/doc/sb4d8l8wb/Fall-2026-COP-4331-002?mode=view"
    assert validate_record(parsed) == []

    parsed["source"]["url"] = "https://fau.simplesyllabus.com/en-US/doc/different/Fall-2026-EEL-3111-001?mode=view"
    assert "source.url document identity does not match source_id" in validate_record(parsed)


def test_browser_probe_stops_first_repeating_denial_and_reports_request_counts():
    session = FakeBrowserSession([
        {"kind": "response", "role": "essential_document", "status": 403},
        {"kind": "response", "role": "essential_document", "status": 403},
    ])
    result = probe_browser_session(session, "https://fau.simplesyllabus.com/doc/exact?mode=view")
    assert result["status"] == "generic_access_denied"
    assert result["stop_reason"] == "essential_access_denied"
    assert result["logical_navigations"] == result["actual_observed_responses"] == result["essential_document_requests"] == 1
    assert session.cancelled and session.closed


def test_playwright_driver_labels_only_identity_or_denial_as_essential():
    assert classify_response_role("https://fau.simplesyllabus.com/api/doc/a4bh2nqsq", 200, "fetch", "a4bh2nqsq") == "essential_document"
    assert classify_response_role("https://fau.simplesyllabus.com/api/bootstrap", 200, "xhr", "a4bh2nqsq") == "other"
    assert classify_response_role("https://fau.simplesyllabus.com/api/bootstrap", 403, "xhr", "a4bh2nqsq") == "essential_document"
    assert classify_response_role("https://sentry.io/store", 429, "fetch", "a4bh2nqsq") == "telemetry"


def test_browser_probe_enforces_essential_failure_budget_separately_from_telemetry():
    session = FakeBrowserSession([
        {"kind": "response", "role": "telemetry", "status": 429},
        {"kind": "response", "role": "essential_document", "status": 500},
        {"kind": "response", "role": "essential_document", "status": 500},
        {"kind": "response", "role": "essential_document", "status": 500},
    ])
    result = probe_browser_session(session, "https://fau.simplesyllabus.com/doc/exact?mode=view", limits=BrowserProbeLimits(essential_failure_budget=2))
    assert result["stop_reason"] == "essential_failure_budget_exhausted"
    assert result["actual_observed_responses"] == 3
    assert result["essential_document_requests"] == 2
    assert result["essential_document_failures"] == 2
    assert result["telemetry_responses"] == 1
    assert session.cancelled and session.closed


def test_successful_essential_initialization_does_not_consume_failure_budget():
    html = (FIXTURES / "rendered_complete.html").read_text(encoding="utf-8")
    session = FakeBrowserSession([
        {"kind": "response", "role": "essential_document", "status": 200},
        {"kind": "response", "role": "essential_document", "status": 204},
        {"kind": "snapshot", "html": html, "final_url": "https://fau.simplesyllabus.com/doc/exact?mode=view"},
    ])
    result = probe_browser_session(session, "https://fau.simplesyllabus.com/doc/exact?mode=view")
    assert result["status"] == "anonymous_full_document"
    assert result["stop_reason"] == "rendered_document_ready"
    assert result["essential_document_requests"] == 2
    assert result["essential_document_failures"] == 0
    assert not session.cancelled and session.closed


def test_browser_probe_enforces_total_response_budget():
    session = FakeBrowserSession([
        {"kind": "response", "role": "other", "status": 200},
        {"kind": "response", "role": "telemetry", "status": 204},
        {"kind": "response", "role": "other", "status": 200},
        {"kind": "response", "role": "other", "status": 200},
    ])
    result = probe_browser_session(session, "https://fau.simplesyllabus.com/doc/exact?mode=view", limits=BrowserProbeLimits(total_response_budget=3))
    assert result["stop_reason"] == "total_response_budget_exhausted"
    assert result["actual_observed_responses"] == 3
    assert session.cancelled and session.closed


def test_browser_probe_enforces_rendered_document_byte_limit():
    session = FakeBrowserSession([
        {"kind": "snapshot", "html": "x" * 2048, "final_url": "https://fau.simplesyllabus.com/doc/exact?mode=view"},
    ])
    result = probe_browser_session(
        session,
        "https://fau.simplesyllabus.com/doc/exact?mode=view",
        limits=BrowserProbeLimits(max_rendered_html_bytes=1024),
    )
    assert result["status"] == "response_too_large"
    assert result["stop_reason"] == "rendered_document_byte_limit_exhausted"
    assert session.cancelled and session.closed


def test_browser_probe_ignores_telemetry_failure_when_rendered_document_is_usable():
    html = (FIXTURES / "rendered_complete.html").read_text(encoding="utf-8")
    session = FakeBrowserSession([
        {"kind": "response", "role": "telemetry", "status": 429},
        {"kind": "snapshot", "html": html, "final_url": "https://fau.simplesyllabus.com/doc/exact?mode=view"},
    ])
    result = probe_browser_session(session, "https://fau.simplesyllabus.com/doc/exact?mode=view")
    assert result["status"] == "anonymous_full_document"
    assert result["stop_reason"] == "rendered_document_ready"
    assert result["telemetry_responses"] == 1
    assert not session.cancelled and session.closed


def test_runtime_full_document_probe_preserves_acquired_status(monkeypatch):
    from backend.syllabi import runtime

    html = (FIXTURES / "rendered_complete.html").read_text(encoding="utf-8")
    session = FakeRuntimeSession(html, runtime_mapping()["view_url"])
    monkeypatch.setenv("SESSION_EVIDENCE_SIGNING_KEY", "offline-runtime-test-signing-key-1234567890")
    monkeypatch.setattr(runtime, "PlaywrightSession", lambda **_kwargs: session)
    monkeypatch.setattr(runtime, "probe_browser_session", lambda *_args, **_kwargs: full_document_probe())

    result = runtime._run_mapping(runtime_mapping())

    assert result["status"] == "acquired"
    assert result["probe_status"] == "anonymous_full_document"
    assert result["record"]["course_code"] == "COP4331"
    assert result["record"]["session_provenance"]["scheme"] == "hmac-sha256-v1"


def test_runtime_reports_invalid_explicit_browser_without_fallback(monkeypatch):
    from backend.syllabi import runtime

    monkeypatch.setenv("SYLLABUS_ACQUISITION_ENABLED", "true")
    monkeypatch.setenv("ACQUISITION_BROWSER_MODE", "headed")
    monkeypatch.setenv("ACQUISITION_CHROME_PATH", "definitely-missing-browser")
    monkeypatch.setattr(runtime, "claim_test_budget", lambda _kind: {"allowed": True, "enforced": False})
    monkeypatch.setattr(runtime, "_mapping", lambda *_args, **_kwargs: runtime_mapping())
    monkeypatch.setattr(
        runtime,
        "_run_mapping",
        lambda _mapping: (_ for _ in ()).throw(
            BrowserExecutableConfigurationError(
                "explicit_browser_executable_invalid",
                "Acquisition browser executable is invalid (explicit).",
            )
        ),
    )

    result = runtime.acquire_exact_syllabus("COP4331", "202608", "002")

    assert result["status"] == "runtime_error"
    assert result["diagnostic"] == "explicit_browser_executable_invalid"
    assert "record" in result and result["record"] is None


def test_synthetic_smoke_uses_complete_runtime_mapping(monkeypatch):
    from backend.syllabi import runtime

    captured = {}

    class SyntheticSession:
        last_html = "<main data-syllabus-document></main>"
        final_url = "http://127.0.0.1:8765/synthetic.html"

    def fake_parse(_html, mapping, source_url):
        captured.update(mapping)
        captured["validated_source_url"] = source_url
        return "acquired", {
            "course_code": "COP4331",
            "term_scope": {"term_id": "202608"},
            "section_scope": {"section": "002"},
            "source": {"source_id": "offline-runtime-smoke"},
        }

    monkeypatch.setenv("RENDER_STARTUP_BROWSER_SMOKE", "true")
    monkeypatch.setattr(runtime, "PlaywrightSession", lambda **_kwargs: SyntheticSession())
    monkeypatch.setattr(runtime, "probe_browser_session", lambda *_args, **_kwargs: {
        "status": "anonymous_full_document", "logical_navigations": 1, "actual_observed_responses": 1,
    })
    monkeypatch.setattr(runtime, "_parse_and_validate_candidate", fake_parse)

    result = runtime.synthetic_smoke("http://127.0.0.1:8765/synthetic.html")

    assert result["status"] == "passed"
    assert result["identity_validated"] is True
    assert captured["view_url"] == "http://127.0.0.1:8765/synthetic.html"
    assert captured["source_document_id"] == "offline-runtime-smoke"
    assert captured["validated_source_url"].startswith("https://fau.simplesyllabus.com/doc/offline-runtime-smoke/")


def test_runtime_discovers_unmapped_exact_syllabus_with_one_application_budget(monkeypatch):
    from backend.syllabi import runtime

    mapping = runtime_mapping(course_code="MAP3305") | {
        "section": "003",
        "source_document_id": "discovered-doc",
        "view_url": "https://fau.simplesyllabus.com/doc/discovered-doc/Fall-2026-MAP-3305-003?mode=view",
    }
    claimed = []
    monkeypatch.setenv("SYLLABUS_ACQUISITION_ENABLED", "true")
    monkeypatch.setenv("ACQUISITION_BROWSER_MODE", "headed")
    monkeypatch.setattr(runtime, "claim_test_budget", lambda kind: claimed.append(kind) or {"allowed": True, "enforced": True, "limit": 1, "used": 1})
    monkeypatch.setattr(runtime, "_mapping", lambda *_args: None)
    monkeypatch.setattr(runtime, "discover_exact_syllabus", lambda *_args: {
        "status": "exact_source_selected",
        "mapping": mapping,
        "logical_navigations": 1,
        "exact_match_count": 1,
        "selection_strategy": "first_exact_course_term_section_match",
    })
    monkeypatch.setattr(runtime, "_run_mapping", lambda selected: {
        "status": "acquired", "record": {"course_code": selected["course_code"]},
        "request_count": 1, "cleanup": "completed",
    })

    result = runtime.acquire_exact_syllabus("MAP3305", "202608", "003")

    assert claimed == ["syllabus"]
    assert result["status"] == "acquired"
    assert result["request_count"] == 2
    assert result["application_acquisition_attempts"] == 1
    assert result["source_discovery"]["status"] == "exact_source_selected"
    assert result["source_discovery"]["exact_match_count"] == 1
    assert "mapping" not in result["source_discovery"]


def test_runtime_exhausted_budget_prevents_discovery_and_document_navigation(monkeypatch):
    from backend.syllabi import runtime

    monkeypatch.setenv("SYLLABUS_ACQUISITION_ENABLED", "true")
    monkeypatch.setenv("ACQUISITION_BROWSER_MODE", "headed")
    monkeypatch.setattr(runtime, "claim_test_budget", lambda _kind: {"allowed": False, "enforced": True, "limit": 0, "used": 0})
    monkeypatch.setattr(runtime, "_mapping", lambda *_args: (_ for _ in ()).throw(AssertionError("mapping lookup should not run")))
    monkeypatch.setattr(runtime, "discover_exact_syllabus", lambda *_args: (_ for _ in ()).throw(AssertionError("discovery should not run")))

    result = runtime.acquire_exact_syllabus("MAP3305", "202608", "003")

    assert result["status"] == "acquisition_budget_exhausted"
    assert result["request_count"] == 0


def test_runtime_full_document_probe_does_not_mask_parser_failure(monkeypatch):
    from backend.syllabi import runtime

    html = (FIXTURES / "rendered_complete.html").read_text(encoding="utf-8")
    session = FakeRuntimeSession(html, runtime_mapping()["view_url"])
    monkeypatch.setattr(runtime, "PlaywrightSession", lambda **_kwargs: session)
    monkeypatch.setattr(runtime, "probe_browser_session", lambda *_args, **_kwargs: full_document_probe())

    result = runtime._run_mapping(runtime_mapping(course_code="CAP4773"))

    assert result["status"] == "course_identity_mismatch"
    assert result["probe_status"] == "anonymous_full_document"
    assert result["record"] is None


def test_runtime_full_document_probe_does_not_mask_candidate_rejection(monkeypatch):
    from backend.syllabi import runtime

    html = (FIXTURES / "rendered_complete.html").read_text(encoding="utf-8")
    session = FakeRuntimeSession(html, runtime_mapping()["view_url"])
    monkeypatch.setattr(runtime, "PlaywrightSession", lambda **_kwargs: session)
    monkeypatch.setattr(runtime, "probe_browser_session", lambda *_args, **_kwargs: full_document_probe())
    monkeypatch.setattr(runtime, "validate_record", lambda _record: ["content identity mismatch"])

    result = runtime._run_mapping(runtime_mapping())

    assert result["status"] == "candidate_rejected"
    assert result["probe_status"] == "anonymous_full_document"
    assert result["record"] is None


def test_browser_probe_cleans_up_on_error_without_touching_accepted_content(tmp_path):
    accepted_path = tmp_path / "accepted.json"
    write_json(accepted_path, accepted([record()]))
    before = accepted_path.read_bytes()
    session = FakeBrowserSession([{"kind": "error", "error": "renderer closed"}])
    with pytest.raises(RuntimeError, match="renderer closed"):
        probe_browser_session(session, "https://fau.simplesyllabus.com/doc/exact?mode=view")
    assert session.cancelled and session.closed
    assert accepted_path.read_bytes() == before


@pytest.mark.parametrize(("term", "section", "error"), [("Spring 2027", "002", "term_identity_mismatch"), ("Fall 2026 1 Full Term", "999", "section_identity_mismatch")])
def test_rejects_wrong_term_or_section_identity(term, section, error):
    html = (FIXTURES / "rendered_complete.html").read_text(encoding="utf-8")
    with pytest.raises(SyllabusParseError) as caught:
        parse_rendered_syllabus(html, course_code="COP4331", term_id="other", term_name=term, section=section, source_document_id="x", source_url="https://fau.simplesyllabus.com/doc/x/name", fetched_at="x", raw_evidence_ref="x")
    assert caught.value.code == error


def test_stable_identity_is_content_independent_and_sections_do_not_collide():
    first, changed, other_section = record(), record(), record("042", "otherdoc")
    changed["document_text"] += " changed"
    assert first["record_id"] == changed["record_id"]
    assert first["record_id"] != other_section["record_id"]


def test_compare_ignores_timestamp_only_but_detects_content_and_access_denied_outcome():
    first = record(); later = deepcopy(first); later["fetched_at"] = "2027-01-01T00:00:00Z"
    assert compare_batches(accepted([first]), batch("later-one", [later]))["unchanged"] == [first["record_id"]]
    later["document_text"] += "\nNew exact text."; later["content_sha256"] = syllabus_content_hash(later)
    diff = compare_batches(accepted([first]), batch("changed-one", [later], [{"course_code": "EEL3111", "status": "generic_access_denied"}]))
    assert diff["changed"] == [first["record_id"]] and diff["generic_access_denied"] == ["EEL3111"]


def test_partial_failure_preserves_accepted_and_acceptance_rollback_are_idempotent(tmp_path):
    first, other = record(), record("042", "otherdoc")
    accepted_path, candidate_path, history = tmp_path / "accepted.json", tmp_path / "candidate.json", tmp_path / "history"
    write_json(accepted_path, accepted([first, other])); write_json(candidate_path, batch("partial-one", [first], [{"course_code": "COP4331", "status": "failed"}]))
    accept_batch(candidate_path, accepted_path, history)
    assert len(read_json(accepted_path)["records"]) == 2
    write_json(candidate_path, batch("partial-two", [deepcopy(first)])); accept_batch(candidate_path, accepted_path, history)
    assert next(x for x in read_json(accepted_path)["records"] if x["record_id"] == first["record_id"])["record_version"] == 1
    rollback_accepted(accepted_path, history, "syllabi-empty")
    assert read_json(accepted_path)["accepted_batch_id"] == "syllabi-empty"


def test_probe_is_bounded_and_stops_on_access_block():
    docs = [{"course_code": "COP4331", "view_url": "https://fau.simplesyllabus.com/doc/x/name"}, {"course_code": "EEL3111", "view_url": "https://fau.simplesyllabus.com/doc/y/name"}]
    calls = 0
    def handler(request):
        nonlocal calls; calls += 1
        return httpx.Response(403, request=request)
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    result = probe_documents(docs, config=FetchConfig(max_retries=0, pace_seconds=0), client=client, sleep=lambda _: None); client.close()
    assert calls == result["live_request_count"] == 1
    assert result["results"][0]["status"] == "generic_access_denied" and result["stopped_on_access_block"] is True
