"""Offline checks for the reusable conversational evaluation harness."""

import subprocess
import sys

from scripts.evaluate_conversational_behavior import (
    CASES_PATH,
    CSV_PATH,
    OFFLINE_CSV_PATH,
    OFFLINE_RESULTS_PATH,
    RESULTS_PATH,
    ROOT,
    deterministic_dataset_evaluation,
    load_json,
    offline_safety_evaluation,
    score_case,
    sanitize_engine_result,
    select_output_paths,
)


def test_matched_expectations_are_bounded_and_cover_required_origins():
    cases = load_json(CASES_PATH)

    assert len(cases) == 12
    assert len({case["case_id"] for case in cases}) == 12
    assert any(case["origin"].startswith("existing:") for case in cases)
    assert any(case["origin"].startswith("added:") for case in cases)
    assert all("adjudication" in case for case in cases)


def test_full_historical_dataset_evaluation_uses_all_labels():
    result = deterministic_dataset_evaluation()

    assert result["total"] == 28
    assert len(result["rows"]) == result["total"]
    assert result["correct"] == 28


def test_offline_forced_failures_and_safety_boundaries_pass():
    checks = offline_safety_evaluation()

    assert len(checks) == 7
    assert all(check["passed"] for check in checks)
    assert {check["check_id"] for check in checks} == {
        "SF-001",
        "SF-002",
        "SF-003",
        "SF-004",
        "SF-005",
        "SF-006",
        "SF-007",
    }


def test_entity_scoring_is_order_insensitive_but_association_exact():
    case = {
        "expected_intents": ["schedule_conflict_check"],
        "expected_entities": {
            "course_codes": ["COP3530C", "MAC2312"],
            "crns": ["17077", "20158"],
            "course_section_pairs": [
                {"course": "COP3530C", "section": "001"},
                {"course": "MAC2312", "section": "006"},
            ],
        },
        "expected_endpoint": {
            "target_handler": "scheduling_engine",
            "disposition": "route_core_engine",
            "engine_executed": True,
            "response_codes": ["SCHEDULE_CONFLICT_FOUND"],
            "required_text": [],
            "forbidden_text": [],
        },
    }
    parsed = {
        "intent": "schedule_conflict_check",
        "course_codes": ["MAC2312", "COP3530C"],
        "crns": ["20158", "17077"],
        "course_section_pairs": [
            {"course": "MAC2312", "section": "006"},
            {"course": "COP3530C", "section": "001"},
        ],
    }
    response = {
        "target_handler": "scheduling_engine",
        "disposition": "route_core_engine",
        "engine_executed": True,
        "response_code": "SCHEDULE_CONFLICT_FOUND",
        "response_text": "",
        "disclaimer": "",
        "explanation_limitations": [],
    }

    scores = score_case(case, parsed, response)

    assert scores["entity_exact"] is True
    assert scores["association_exact"] is True


def test_saved_live_evidence_is_bounded_and_distinguishes_fallback():
    results = load_json(RESULTS_PATH)
    live_rows = results["matched"]["live"]

    assert results["evaluated_commit"] == "c1fc9e7918e8db39bfa722d78039e5c16844812b"
    assert results["live_run"]["attempts"] == 12
    assert len(live_rows) == 12
    assert all(row["validated_parse"]["parser_source"] == "llm" for row in live_rows)
    assert all(row["validated_parse"]["fallback_used"] is False for row in live_rows)
    assert results["live_run"]["not_run"] == []


def test_default_offline_run_cannot_replace_recorded_live_evidence():
    before_json = RESULTS_PATH.read_bytes()
    before_csv = CSV_PATH.read_bytes()

    selected_json, selected_csv = select_output_paths(
        live=False, requested_output=None, overwrite_live_evidence=False
    )
    assert selected_json == OFFLINE_RESULTS_PATH
    assert selected_csv == OFFLINE_CSV_PATH

    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/evaluate_conversational_behavior.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert OFFLINE_RESULTS_PATH.exists()
    assert OFFLINE_CSV_PATH.exists()
    assert RESULTS_PATH.read_bytes() == before_json
    assert CSV_PATH.read_bytes() == before_csv


def test_explicit_offline_live_evidence_overwrite_requires_approval_flag():
    try:
        select_output_paths(
            live=False,
            requested_output=RESULTS_PATH,
            overwrite_live_evidence=False,
        )
    except ValueError as exc:
        assert "--overwrite-live-evidence" in str(exc)
    else:
        raise AssertionError("Canonical live evidence overwrite was not blocked")


def test_engine_result_sanitizer_removes_profile_history_but_keeps_facts():
    sanitized = sanitize_engine_result(
        {
            "student_id": "synthetic-id",
            "student_name": "synthetic-name",
            "major": "synthetic-major",
            "completed_courses": ["PRIVATE101"],
            "assessment": "Manageable",
            "nested": {"recent_courses": ["PRIVATE102"], "has_conflict": False},
        }
    )

    assert sanitized == {
        "assessment": "Manageable",
        "nested": {"has_conflict": False},
    }
