from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import httpx
import pytest

from backend.course_descriptions.http import FetchConfig
from backend.course_descriptions.models import SCHEMA_VERSION, read_json, write_json
from backend.course_descriptions.storage import compare_batches
from backend.syllabi.models import syllabus_content_hash
from backend.syllabi.parser import SyllabusParseError, classify_page, parse_rendered_syllabus
from backend.syllabi.probe import probe_documents
from backend.syllabi.storage import accept_batch, rollback_accepted, validate_batch

FIXTURES = Path(__file__).parent / "syllabi" / "fixtures"


def record(section="002", source_id="sb4d8l8wb"):
    return parse_rendered_syllabus((FIXTURES / "rendered_complete.html").read_text(encoding="utf-8"), course_code="COP4331", term_id="202608", term_name="Fall 2026 1 Full Term", section=section, source_document_id=source_id, source_url=f"https://fau.simplesyllabus.com/doc/{source_id}/COP-4331?mode=view", fetched_at="2026-10-30T12:00:00Z", raw_evidence_ref="tests/syllabi/fixtures/rendered_complete.html", instructor="Ionut Cardei")


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
    assert validate_batch(batch("parsed-one", [item]))["valid"] is True


def test_rejects_library_shell_login_redirect_and_missing_or_ambiguous_text():
    shell = (FIXTURES / "library_shell.html").read_text(encoding="utf-8")
    assert classify_page(shell, "https://fau.simplesyllabus.com/en-US/syllabus-library") == "library_shell"
    assert classify_page("<p>Sign in</p>", "https://fau.simplesyllabus.com/login") == "restricted"
    assert classify_page("", "https://fau.simplesyllabus.com/doc/x/name", 403) == "restricted"
    with pytest.raises(SyllabusParseError):
        parse_rendered_syllabus("<main><h1>COP 4331</h1></main>", course_code="COP4331", term_id="202608", term_name="Fall", section="002", source_document_id="x", source_url="https://fau.simplesyllabus.com/doc/x/name", fetched_at="x", raw_evidence_ref="x")
    duplicate = "<main><h1>COP 4331</h1><h2>Topics</h2><p>One</p><h2>Topics</h2><p>Two</p></main>"
    with pytest.raises(SyllabusParseError) as caught:
        parse_rendered_syllabus(duplicate, course_code="COP4331", term_id="202608", term_name="Fall", section="002", source_document_id="x", source_url="https://fau.simplesyllabus.com/doc/x/name", fetched_at="x", raw_evidence_ref="x")
    assert caught.value.code == "ambiguous_academic_text"


def test_stable_identity_is_content_independent_and_sections_do_not_collide():
    first, changed, other_section = record(), record(), record("042", "otherdoc")
    changed["document_text"] += " changed"
    assert first["record_id"] == changed["record_id"]
    assert first["record_id"] != other_section["record_id"]


def test_compare_ignores_timestamp_only_but_detects_content_and_restricted_outcome():
    first = record(); later = deepcopy(first); later["fetched_at"] = "2027-01-01T00:00:00Z"
    assert compare_batches(accepted([first]), batch("later-one", [later]))["unchanged"] == [first["record_id"]]
    later["document_text"] += "\nNew exact text."; later["content_sha256"] = syllabus_content_hash(later)
    diff = compare_batches(accepted([first]), batch("changed-one", [later], [{"course_code": "EEL3111", "status": "restricted"}]))
    assert diff["changed"] == [first["record_id"]] and diff["restricted"] == ["EEL3111"]


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
    assert result["results"][0]["status"] == "restricted" and result["stopped_on_access_block"] is True
