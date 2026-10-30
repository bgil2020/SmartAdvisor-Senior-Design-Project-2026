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
from backend.syllabi.probe import probe_documents
from backend.syllabi.storage import accept_batch, rollback_accepted, validate_batch

FIXTURES = Path(__file__).parent / "syllabi" / "fixtures"


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


def test_browser_probe_enforces_essential_budget_separately_from_telemetry():
    session = FakeBrowserSession([
        {"kind": "response", "role": "telemetry", "status": 429},
        {"kind": "response", "role": "essential_document", "status": 500},
        {"kind": "response", "role": "essential_document", "status": 500},
        {"kind": "response", "role": "essential_document", "status": 500},
    ])
    result = probe_browser_session(session, "https://fau.simplesyllabus.com/doc/exact?mode=view", limits=BrowserProbeLimits(essential_request_budget=2))
    assert result["stop_reason"] == "essential_request_budget_exhausted"
    assert result["actual_observed_responses"] == 3
    assert result["essential_document_requests"] == 2
    assert result["telemetry_responses"] == 1
    assert session.cancelled and session.closed


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
