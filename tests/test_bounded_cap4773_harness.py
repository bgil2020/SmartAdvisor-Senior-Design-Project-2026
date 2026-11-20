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
    }, code_state={"tested_head": "test-head", "tracked_changes_present": False})

    assert diagnostics["acquisition"]["final_status"] == "course_identity_mismatch"
    assert diagnostics["acquisition"]["probe_status"] == "anonymous_full_document"
    assert diagnostics["acquisition"]["observed_browser_responses"] == 23
    assert diagnostics["evidence"]["backend_acceptance_via_follow_up"] == "unknown"
    assert diagnostics["citation"]["rendered"] == "unknown"
    assert diagnostics["tested_head"] == "test-head"
    assert diagnostics["combined_harness_uncommitted"] is False
    assert diagnostics["provider"] == {
        "model": "gemini-3.5-flash-lite",
        "request_budget": 1,
        "accepted_provider_answers": 0,
        "automatic_retries": 0,
    }


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


def test_support_check_accepts_equivalent_decimal_percent_and_range_formatting():
    record = {
        "course_code": "CAP4773",
        "term_scope": {"term_id": "202608"},
        "section_scope": {"section": "001"},
        "academic_sections": [{
            "locator": "heading:Course Grading Scale",
            "text": "A is 90.0% to 100.00%.",
        }],
    }
    result = harness.support_check({
        "response_text": "For CAP 4773, section 001, A is 90–100. [source-202608-1]",
        "citations": [{"source_id": "source-202608-1", "locator": "heading:Course Grading Scale"}],
    }, record)

    assert result["passed"] is True
    assert result["numeric_claim_count"] == 2
    assert result["numeric_claims_supported"] is True
    assert result["unsupported_numeric_values"] == []
    assert result["grade_range_claim_count"] == 1
    assert result["unsupported_grade_ranges"] == []


def test_course_codes_terms_sections_and_citation_ids_are_not_numeric_claims():
    record = {
        "course_code": "CAP4773",
        "term_scope": {"term_id": "202608"},
        "section_scope": {"section": "001"},
        "academic_sections": [{"locator": "heading:Summary", "text": "The grading scale is listed."}],
    }
    result = harness.support_check({
        "response_text": "CAP 4773 term 202608 section 001 has a grading scale. [rag:cap4773:202608:001:42]",
        "citations": [{"source_id": "rag:cap4773:202608:001:42", "locator": "heading:Summary"}],
    }, record)

    assert result["passed"] is True
    assert result["numeric_claim_count"] == 0


def test_incorrect_grade_boundary_is_rejected():
    record = {
        "academic_sections": [{"locator": "heading:Scale", "text": "A: 90% to 100%."}],
    }
    result = harness.support_check({
        "response_text": "A: 89% to 100%. [source-1]",
        "citations": [{"source_id": "source-1", "locator": "heading:Scale"}],
    }, record)

    assert result["passed"] is False
    assert result["numeric_claims_supported"] is False
    assert result["unsupported_numeric_values"] == ["89"]


def test_correct_numbers_attached_to_wrong_grade_are_rejected():
    record = {
        "academic_sections": [{
            "locator": "heading:Scale",
            "text": "A\t90% to 100%\nB\t80% to 89%",
        }],
    }
    result = harness.support_check({
        "response_text": "B: 90% to 100%. [source-1]",
        "citations": [{"source_id": "source-1", "locator": "heading:Scale"}],
    }, record)

    assert result["numeric_claims_supported"] is True
    assert result["passed"] is False
    assert result["unsupported_grade_ranges"][0]["grade"] == "B"
    assert result["unsupported_grade_ranges"][0]["low"] == "90"
    assert result["unsupported_grade_ranges"][0]["high"] == "100"
    assert result["source_relationship_extraction"] == "succeeded"
    assert result["grade_relationship_comparison"][0]["status"] == "mismatch"


def test_correct_percentage_attached_to_wrong_category_is_rejected():
    record = {
        "academic_sections": [{
            "locator": "heading:Weights",
            "text": "Homework: 20.0%; Exams: 80%.",
        }],
    }
    result = harness.support_check({
        "response_text": "Exams: 20%. [source-1]",
        "citations": [{"source_id": "source-1", "locator": "heading:Weights"}],
    }, record)

    assert result["numeric_claims_supported"] is True
    assert result["passed"] is False
    assert result["unsupported_category_percentages"] == [{"category": "exams", "percentage": "20"}]


def test_support_is_resolved_only_from_the_cited_evidence_locator():
    record = {
        "academic_sections": [
            {"locator": "heading:Cited", "text": "A: 90% to 100%."},
            {"locator": "heading:Uncited", "text": "B: 80% to 89%."},
        ],
    }
    result = harness.support_check({
        "response_text": "B: 80% to 89%. [source-1]",
        "citations": [{"source_id": "source-1", "locator": "heading:Cited"}],
    }, record)

    assert result["cited_locators_resolved"] is True
    assert result["passed"] is False
    assert result["unsupported_numeric_values"] == ["80", "89"]


def test_failed_source_relationship_extraction_is_inconclusive_not_mismatch():
    record = {
        "academic_sections": [{
            "locator": "heading:Course Grading Scale",
            "text": "A90% - 100%B80% - 89%",
        }],
    }
    result = harness.support_check({
        "response_text": "A: 90% to 100%. [source-1]",
        "citations": [{"source_id": "source-1", "locator": "heading:Course Grading Scale"}],
    }, record)

    assert result["answer_grade_relationship_count"] == 1
    assert result["source_grade_relationship_count"] == 0
    assert result["source_relationship_extraction"] == "indeterminate"
    assert result["unsupported_grade_ranges"] == []
    assert result["unverified_grade_relationships"][0]["grade"] == "A"
    assert result["grade_relationship_comparison"][0]["status"] == "unknown"
    assert result["passed"] is False


def test_equivalent_interval_range_and_threshold_notation_match_without_losing_operators():
    record = {
        "academic_sections": [{
            "locator": "heading:Scale",
            "text": "A: [90.0%, 100.00%]\nF: < 60.0%",
        }],
    }
    result = harness.support_check({
        "response_text": "A: 90 to 100; F: less than 60. [source-1]",
        "citations": [{"source_id": "source-1", "locator": "heading:Scale"}],
    }, record)

    assert result["source_relationship_extraction"] == "succeeded"
    assert result["answer_grade_relationship_count"] == 2
    assert result["source_grade_relationship_count"] == 2
    assert [item["status"] for item in result["grade_relationship_comparison"]] == ["match", "match"]
    threshold = next(item for item in result["grade_relationship_comparison"] if item["grade"] == "F")
    assert threshold["source_relationships"][0]["operator"] == "<"
    assert threshold["answer_relationship"]["operator"] == "<"
    assert result["passed"] is True


@pytest.mark.parametrize(
    ("source_text", "expected"),
    [
        ("A\t90% - 100%\nB+\t87% - 89%", [("A", "90", "100"), ("B+", "87", "89")]),
        ("90.0% through 100.00%\tA\n87%–89%\tB+", [("A", "90", "100"), ("B+", "87", "89")]),
    ],
)
def test_relationship_extractor_supports_representative_table_orders(source_text, expected):
    relationships = harness._grade_relationships(source_text)
    assert [(item["grade"], item["low"], item["high"]) for item in relationships] == expected


def test_explicit_endpoint_inclusivity_conflict_is_rejected():
    record = {
        "academic_sections": [{"locator": "heading:Scale", "text": "A: [90, 100]"}],
    }
    result = harness.support_check({
        "response_text": "A: (90, 100]. [source-1]",
        "citations": [{"source_id": "source-1", "locator": "heading:Scale"}],
    }, record)

    assert result["numeric_claims_supported"] is True
    assert result["grade_relationship_comparison"][0]["status"] == "mismatch"
    assert result["grade_relationship_comparison"][0]["source_relationships"][0]["low_inclusive"] is True
    assert result["grade_relationship_comparison"][0]["answer_relationship"]["low_inclusive"] is False
    assert result["passed"] is False


def test_relationship_diagnostics_are_minimal_and_exclude_raw_text():
    source_sentence = "A is 90% to 100%; explanatory source prose is private to the comparison."
    answer_sentence = "A is 90 to 100; explanatory answer prose is not persisted. [source-1]"
    result = harness.support_check({
        "response_text": answer_sentence,
        "citations": [{"source_id": "source-1", "locator": "heading:Scale"}],
    }, {"academic_sections": [{"locator": "heading:Scale", "text": source_sentence}]})
    serialized = json.dumps(result)

    assert result["source_grade_relationship_count"] == 1
    assert result["answer_grade_relationship_count"] == 1
    assert result["grade_relationship_comparison"][0]["status"] == "match"
    assert source_sentence not in serialized
    assert answer_sentence not in serialized
    assert "explanatory source prose" not in serialized
    assert "explanatory answer prose" not in serialized


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
    assert len(writes) >= 2
    assert max(writes[:2]) < source.index("require(response.status == 200")


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


def test_grade_diagnostic_harness_is_inert_without_explicit_approval(monkeypatch):
    monkeypatch.setattr(harness.argparse.ArgumentParser, "parse_args", lambda _self: type("Args", (), {"approved_live_grade_diagnostic": False})())
    monkeypatch.setattr(harness.asyncio, "run", lambda *_args, **_kwargs: pytest.fail("live harness should not run"))
    with pytest.raises(RuntimeError, match="explicit approval"):
        harness.main()


def test_grade_diagnostic_execute_configures_one_provider_call_and_no_retries():
    source = inspect.getsource(harness.execute)
    assert '"RAG_GENERATION_MODE": "gemini"' in source
    assert '"GEMINI_MODEL": MODEL' in source
    assert '"GEMINI_TIMEOUT_SECONDS": "10"' in source
    assert '"GEMINI_MAX_OUTPUT_TOKENS": "512"' in source
    assert '"GEMINI_TEST_REQUEST_BUDGET": "1"' in source
    assert '"ACQUISITION_TEST_CATALOG_BUDGET": "0"' in source
    assert '"ACQUISITION_TEST_SYLLABUS_BUDGET": "1"' in source
    assert "preflight(require_provider_key=True)" in source
    assert "Expected exactly one UI conversation submission" in source
    assert "Which letter grade ranges" not in source
