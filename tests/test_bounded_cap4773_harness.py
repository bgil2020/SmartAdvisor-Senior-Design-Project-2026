from __future__ import annotations

import json
import inspect
from pathlib import Path

import pytest

from scripts import verify_bounded_cap4773_ui as harness

sanitized_diagnostics = harness.sanitized_diagnostics


def test_harness_sanitizer_preserves_status_counts_and_validation_metadata():
    diagnostics = sanitized_diagnostics({
        "status": "acquisition_failed",
        "response_code": "SOURCE_ACQUISITION_UNAVAILABLE",
        "source_scope": {"course_code": "CAP4773", "term_id": "202608", "section": "001"},
        "acquisition": {
            "status": "course_identity_mismatch",
            "probe_status": "anonymous_full_document",
            "request_count": 1,
            "actual_observed_responses": 23,
            "essential_document_failures": 0,
        },
    })

    assert diagnostics["acquisition"]["final_status"] == "course_identity_mismatch"
    assert diagnostics["acquisition"]["probe_status"] == "anonymous_full_document"
    assert diagnostics["acquisition"]["observed_browser_responses"] == 23
    assert diagnostics["evidence"]["backend_acceptance_via_follow_up"] == "unknown"
    assert diagnostics["citation"]["rendered"] == "unknown"


def test_harness_sanitizer_never_persists_raw_text_prompt_or_signature():
    diagnostics = sanitized_diagnostics({
        "status": "grounded_answer",
        "response_text": "sensitive answer excerpt",
        "raw_message": "private prompt",
        "acquisition": {"status": "acquired", "probe_status": "anonymous_full_document"},
        "acquired_evidence": [{
            "record_id": "record-1",
            "record_category": "syllabus",
            "course_code": "CAP4773",
            "document_text": "raw syllabus body",
            "academic_sections": [{"heading": "Grading", "text": "raw section body"}],
            "source": {"source_id": "fjhz2vvga", "url": "https://fau.simplesyllabus.com/doc/fjhz2vvga/example"},
            "session_provenance": {"scheme": "hmac-sha256-v1", "signature": "secret-signature"},
        }],
    })
    serialized = json.dumps(diagnostics)

    assert "sensitive answer excerpt" not in serialized
    assert "private prompt" not in serialized
    assert "raw syllabus body" not in serialized
    assert "raw section body" not in serialized
    assert "secret-signature" not in serialized
    assert diagnostics["evidence"]["signature_present"] is True
    assert diagnostics["evidence"]["document_character_count"] == len("raw syllabus body")


def test_follow_up_sanitizer_records_backend_acceptance_and_zero_reacquisition():
    follow_up = harness.sanitized_follow_up({
        "status": "grounded_answer",
        "response_code": "SESSION_EVIDENCE_ANSWER",
        "source_scope": {"course_code": "CAP4773", "term_id": "202608", "section": "001"},
        "acquisition": {
            "status": "not_needed",
            "additional_source_acquisitions": 0,
            "session_evidence_submitted": 1,
            "session_evidence_accepted": 1,
            "session_evidence_matched": 1,
            "session_evidence_reused": True,
        },
        "citations": [{
            "record_id": "fau-simple-syllabus:syllabus:cap4773:202608:001:fjhz2vvga",
            "url": "https://fau.simplesyllabus.com/doc/fjhz2vvga/example",
            "locator": "heading:Course Grading Scale",
        }],
    })

    assert follow_up["acquisition_status"] == "not_needed"
    assert follow_up["additional_source_acquisitions"] == 0
    assert follow_up["session_evidence_submitted"] == 1
    assert follow_up["session_evidence_accepted"] == 1
    assert follow_up["session_evidence_matched"] == 1
    assert follow_up["session_evidence_reused"] is True
    assert follow_up["citation_url_matches_document"] is True


def test_failure_diagnostics_are_written_and_execution_persists_before_assertions(tmp_path, monkeypatch):
    evidence_path = tmp_path / "failure.json"
    monkeypatch.setattr(harness, "EVIDENCE_PATH", evidence_path)
    diagnostics = sanitized_diagnostics({
        "acquisition": {
            "status": "course_identity_mismatch",
            "probe_status": "anonymous_full_document",
            "actual_observed_responses": 25,
        },
    })
    harness.write_diagnostics(diagnostics)
    with pytest.raises(RuntimeError):
        harness.require(False, "offline forced assertion")

    saved = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert saved["acquisition"]["final_status"] == "course_identity_mismatch"
    assert saved["acquisition"]["observed_browser_responses"] == 25
    source = inspect.getsource(harness.execute)
    writes = []
    offset = 0
    while (index := source.find("write_diagnostics(diagnostics)", offset)) >= 0:
        writes.append(index)
        offset = index + 1
    assert writes[0] < source.index("require(response.status == 200")
    assert writes[1] < source.index("require(follow_response.status == 200")


def test_preflight_failure_occurs_before_local_process_or_source_capable_browser_start(tmp_path, monkeypatch):
    called = False

    def unexpected_run(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("offline test runner should not start")

    monkeypatch.setattr(harness, "CHROME_PATH", Path(tmp_path / "missing-chrome.exe"))
    monkeypatch.setattr(harness.subprocess, "run", unexpected_run)
    with pytest.raises(RuntimeError, match="Chrome"):
        harness.preflight()
    assert called is False


def test_cleanup_helper_accepts_an_already_stopped_process(monkeypatch):
    class StoppedProcess:
        def poll(self):
            return 0

    monkeypatch.setattr(harness.subprocess, "run", lambda *_args, **_kwargs: pytest.fail("taskkill should not run"))
    assert harness.stop_tree(StoppedProcess()) is True
