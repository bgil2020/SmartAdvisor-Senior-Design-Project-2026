"""Focused diagnostic test suite for backend-only integration audit.

Audits conversational routing, entity extraction, context validation,
and engine execution across all required test cases (A through J).
Preserves existing tests untouched.
"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.api import app
import backend.conversational_router as conv_router
from backend.compatibility_engine import evaluate_compatibility
from backend.overlap_detector import sections_overlap, get_conflict_details
from backend.alternative_section_search import find_alternative_sections
from backend.section_retriever import load_course_data, get_section_by_crn

client = TestClient(app)


# ----------------------------------------------------------------------
# Standalone Engine Baseline Verification
# ----------------------------------------------------------------------

def test_standalone_compatibility_engine_direct():
    """Verify that evaluate_compatibility works when invoked directly."""
    result = evaluate_compatibility(
        student_id="Z24567901",
        proposed_courses=["COP4331", "MAP3305"],
        recent_difficulty=1,
        satisfied_with_performance="yes",
        work_hours=5.0,
        preferred_max_credits=15.0,
        recent_courses=["CDA4240C", "CDA4102", "MAC2313"],
    )
    assert result["success"] is True
    assert result["student_id"] == "Z24567901"
    assert "assessment" in result
    assert result["proposed_credits"] > 0


def test_standalone_scheduling_overlap_direct():
    """Verify that overlap_detector functions work when invoked directly."""
    df = load_course_data()
    # CRN 20158: COP 3530C sect 001 TR 12:30 PM - 01:50 PM
    # CRN 17077: MAC 2312 sect 006 TR 12:00 PM - 01:50 PM
    s1 = get_section_by_crn(df, "20158")
    s2 = get_section_by_crn(df, "17077")
    assert s1 is not None and s2 is not None
    assert sections_overlap(s1, s2) is True
    details = get_conflict_details(s1, s2)
    assert details["conflict"] == "Yes"
    assert "T" in details["shared_days"]


def test_standalone_alternative_search_direct():
    """Verify that find_alternative_sections works when invoked directly."""
    df = load_course_data()
    alts = find_alternative_sections(
        courses=df,
        conflicted_crn="20158",
        selected_crns=["17077"],
        max_results=3,
    )
    assert len(alts) > 0
    # Alternatives should be different sections of the same course COP 3530C
    for alt in alts:
        assert str(alt["CRN"]).strip() != "20158"
        assert alt["COURSE"] == "COP 3530C"


# ----------------------------------------------------------------------
# Conversational Integration: Cases A through J
# ----------------------------------------------------------------------

def test_case_a_complete_compatibility_request():
    """Case A: Complete course compatibility request genuinely executes the engine."""
    payload = {
        "message": "Can I take COP 4331 and MAP 3305 together?",
        "student_id": "Z24567901",
        "recent_difficulty": 1,
        "satisfied_with_performance": "yes",
        "work_hours": 5.0,
        "preferred_max_credits": 15.0,
        "recent_courses": ["CDA4240C", "CDA4102", "MAC2313"],
    }
    real_fn = conv_router.evaluate_compatibility
    calls = []

    def spy_fn(*args, **kwargs):
        calls.append((args, kwargs))
        return real_fn(*args, **kwargs)

    with patch.object(conv_router, "evaluate_compatibility", side_effect=spy_fn):
        resp = client.post("/conversation", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert len(calls) == 1
    assert data["status"] == "engine_executed"
    assert data["target_handler"] == "course_compatibility_engine"
    assert data["engine_executed"] is True
    assert data["response_code"] == "COMPATIBILITY_EVALUATION_COMPLETE"
    assert "COP4331" in data["extracted_courses"]
    assert "MAP3305" in data["extracted_courses"]
    assert data["engine_result"] is not None
    assert data["engine_result"]["success"] is True

    # Compare with authoritative standalone engine output
    authoritative = real_fn(
        student_id=payload["student_id"],
        proposed_courses=["COP4331", "MAP3305"],
        recent_difficulty=payload["recent_difficulty"],
        satisfied_with_performance=payload["satisfied_with_performance"],
        work_hours=payload["work_hours"],
        preferred_max_credits=payload["preferred_max_credits"],
        recent_courses=payload["recent_courses"],
    )
    assert data["engine_result"]["assessment"] == authoritative["assessment"]
    assert data["engine_result"]["proposed_credits"] == authoritative["proposed_credits"]


def test_case_b_missing_context_compatibility_request():
    """Case B: Compatibility request missing student/workload context does NOT call engine."""
    payload = {
        "message": "Can I take COP 4331 and MAP 3305 together?",
        # No student_id or workload fields
    }
    with patch.object(conv_router, "evaluate_compatibility") as mock_engine:
        resp = client.post("/conversation", json=payload)
        mock_engine.assert_not_called()

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "clarification"
    assert data["target_handler"] == "course_compatibility_engine"
    assert data["response_code"] == "MISSING_STUDENT_CONTEXT"
    assert data["engine_executed"] is False
    assert "student_id" in data["missing_context"]
    assert "work_hours" in data["missing_context"]
    assert data["engine_result"] is None
    # Note contract anomaly: safe_to_route is True even though status is clarification
    assert data["safe_to_route"] is True


def test_case_c1_scheduling_conflict_real_overlapping_pair():
    """Case C1: Real overlapping sections execute overlap detector and return conflict outcome."""
    payload = {
        "message": "Do COP 3530C section 001 and MAC 2312 section 006 overlap?",
    }
    real_overlap = conv_router.evaluate_schedule_conflict
    calls = []

    def spy_conflict(*args, **kwargs):
        calls.append((args, kwargs))
        return real_overlap(*args, **kwargs)

    with patch.object(conv_router, "evaluate_schedule_conflict", side_effect=spy_conflict):
        resp = client.post("/conversation", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert len(calls) == 1
    assert data["status"] == "engine_executed"
    assert data["target_handler"] == "scheduling_engine"
    assert data["response_code"] == "SCHEDULE_CONFLICT_FOUND"
    assert data["engine_executed"] is True
    assert data["engine_result"]["has_conflict"] is True
    assert "T, R" in data["engine_result"]["shared_days"]


def test_case_c2_scheduling_conflict_real_non_overlapping_pair():
    """Case C2: Real non-overlapping sections execute overlap detector and return no-conflict outcome."""
    payload = {
        "message": "Do COP 3530C section 001 and MAC 2312 section 002 overlap?",
    }
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "engine_executed"
    assert data["target_handler"] == "scheduling_engine"
    assert data["response_code"] == "NO_SCHEDULE_CONFLICT"
    assert data["engine_executed"] is True
    assert data["engine_result"]["has_conflict"] is False


def test_case_c3_scheduling_conflict_missing_section_clarification():
    """Case C3: Conflict query missing section numbers returns clarification without engine call."""
    payload = {
        "message": "Do COP 3530C and MAC 2312 overlap?",
    }
    with patch.object(conv_router, "evaluate_schedule_conflict") as mock_engine:
        resp = client.post("/conversation", json=payload)
        mock_engine.assert_not_called()

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "clarification"
    assert data["response_code"] in ["MISSING_SCHEDULE_DETAILS", "MISSING_SECTION_DETAILS"]
    assert data["engine_executed"] is False


def test_case_c4_scheduling_conflict_course_suffix_handling():
    """Case C4: Query without course suffix 'C' returns clear not-found validation error without silent equating."""
    payload = {
        "message": "Do COP 3530 section 001 and MAC 2312 section 006 overlap?",
    }
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "engine_error"
    assert data["response_code"] == "SECTION_NOT_FOUND"
    assert data["engine_executed"] is False
    assert "COP 3530C" in data["response_text"]


def test_case_c5_scheduling_conflict_unknown_section_crn():
    """Case C5: Unknown CRN returns clear validation error."""
    payload = {
        "message": "Do CRN 99999 and CRN 17077 overlap?",
    }
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "engine_error"
    assert data["response_code"] == "SECTION_NOT_FOUND"
    assert data["engine_executed"] is False


def test_case_c6_scheduling_conflict_engine_exception():
    """Case C6: Exception in conflict engine is caught, logged, and returned as safe engine_error."""
    payload = {
        "message": "Do COP 3530C section 001 and MAC 2312 section 006 overlap?",
    }

    def failing_conflict(*args, **kwargs):
        raise RuntimeError("Simulated internal overlap crash")

    with patch.object(conv_router, "evaluate_schedule_conflict", side_effect=failing_conflict):
        resp = client.post("/conversation", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "engine_error"
    assert data["response_code"] == "ENGINE_EXECUTION_ERROR"
    assert data["engine_executed"] is False
    assert "Simulated internal overlap crash" not in data["response_text"]  # Safe user message


def test_case_d1_alternative_section_with_schedule_context():
    """Case D1: Alternative section search with enrolled schedule executes engine and matches direct output."""
    payload = {
        "message": "Find another section of COP 3530C section 001 that fits around my schedule.",
        "target_section": "20158",
        "selected_sections": ["17077"],
    }
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "engine_executed"
    assert data["target_handler"] == "scheduling_engine"
    assert data["response_code"] == "ALTERNATIVE_SECTIONS_FOUND"
    assert data["engine_executed"] is True
    assert data["engine_result"]["count"] == 2

    # Compare against direct standalone engine execution
    df = load_course_data()
    direct_alts = find_alternative_sections(df, conflicted_crn="20158", selected_crns=["17077"], max_results=3)
    assert len(data["engine_result"]["alternatives"]) == len(direct_alts)
    returned_crns = [a["crn"] for a in data["engine_result"]["alternatives"]]
    direct_crns = [str(a["CRN"]).replace(".0", "") for a in direct_alts]
    assert returned_crns == direct_crns


def test_case_d2_alternative_section_explicitly_empty_schedule():
    """Case D2: Alternative section search with explicitly empty schedule ([]) executes successfully."""
    payload = {
        "message": "Find another section of COP 3530C section 001.",
        "target_section": "20158",
        "selected_sections": [],  # Explicitly empty schedule
    }
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "engine_executed"
    assert data["response_code"] == "ALTERNATIVE_SECTIONS_FOUND"
    assert data["engine_executed"] is True
    assert data["engine_result"]["count"] > 0


def test_case_d3_alternative_section_missing_schedule_clarification():
    """Case D3: Alternative section search with omitted schedule (None) asks for clarification."""
    payload = {
        "message": "Find another section of COP 3530C section 001 that fits around my schedule.",
        "target_section": "20158",
        # selected_sections omitted
    }
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "clarification"
    assert data["response_code"] == "MISSING_SCHEDULE_CONTEXT"
    assert data["engine_executed"] is False
    assert "selected_sections" in data["missing_context"]


def test_case_d4_alternative_section_missing_target_clarification():
    """Case D4: Alternative section search with no target section or course asks for clarification."""
    payload = {
        "message": "Find another section that fits around my schedule.",
        "selected_sections": ["17077"],
    }
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "clarification"
    assert data["response_code"] in ["MISSING_COURSE_CODES", "MISSING_TARGET_SECTION"]
    assert data["engine_executed"] is False


def test_case_d5_alternative_section_unknown_identifier():
    """Case D5: Unknown target section returns clear validation error."""
    payload = {
        "message": "Find another section to replace CRN 99999.",
        "target_section": "99999",
        "selected_sections": ["17077"],
    }
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "engine_error"
    assert data["response_code"] == "SECTION_NOT_FOUND"
    assert data["engine_executed"] is False


def test_case_d6_alternative_section_no_valid_alternatives_outcome():
    """Case D6: When no alternative sections are open/available, returns valid engine execution with count=0."""
    # Force find_alternative_sections to return empty list
    with patch("backend.scheduling_service.find_alternative_sections", return_value=[]):
        payload = {
            "message": "Find another section of COP 3530C section 001.",
            "target_section": "20158",
            "selected_sections": [],
        }
        resp = client.post("/conversation", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "engine_executed"
    assert data["response_code"] == "NO_ALTERNATIVE_SECTIONS_FOUND"
    assert data["engine_executed"] is True
    assert data["engine_result"]["count"] == 0
    assert data["engine_result"]["alternatives"] == []


def test_case_d7_alternative_section_engine_exception():
    """Case D7: Engine exception in alternative section search is caught and returned as engine_error."""
    def failing_alts(*args, **kwargs):
        raise RuntimeError("Simulated alternatives crash")

    with patch("backend.scheduling_service.find_alternative_sections", side_effect=failing_alts):
        payload = {
            "message": "Find another section of COP 3530C section 001.",
            "target_section": "20158",
            "selected_sections": [],
        }
        resp = client.post("/conversation", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "engine_error"
    assert data["response_code"] == "ENGINE_EXECUTION_ERROR"
    assert data["engine_executed"] is False


def test_case_e_online_override_screening_not_integrated():
    """Case E: Online override screening routes to UI form redirect, no backend engine exists."""
    payload = {
        "message": "Can I take COP 3330 online because I work full time?",
    }
    with patch.object(conv_router, "evaluate_compatibility") as mock_comp:
        resp = client.post("/conversation", json=payload)
        mock_comp.assert_not_called()

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "engine_unavailable"
    assert data["target_handler"] == "online_override_eligibility_engine"
    assert data["response_code"] == "OVERRIDE_DIRECTED_TO_UI"
    assert data["engine_executed"] is False
    assert data["engine_result"] is None
    assert "Online Course Override Evaluator" in data["response_text"]


def test_case_f_advisor_escalation_official_actions():
    """Case F: Official approval / registration requests escalate to advisor without engine call."""
    payloads = [
        {"message": "Can you approve my override for COP 3530?"},
        {"message": "Please register me for COP 3530."},
        {"message": "Can you guarantee I will graduate on time?"},
    ]
    for p in payloads:
        with patch.object(conv_router, "evaluate_compatibility") as mock_comp:
            resp = client.post("/conversation", json=p)
            mock_comp.assert_not_called()

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "escalation"
        assert data["target_handler"] == "academic_advisor"
        assert data["response_code"] == "ADVISOR_ESCALATION_REQUIRED"
        assert data["safe_to_route"] is False
        assert data["engine_executed"] is False
        assert data["engine_result"] is None


def test_case_g_informational_future_rag_candidate():
    """Case G: Informational inquiries remain safely RAG-inactive without engine execution."""
    payload = {
        "message": "What topics are covered in COP 3530?",
    }
    with patch.object(conv_router, "evaluate_compatibility") as mock_comp:
        resp = client.post("/conversation", json=payload)
        mock_comp.assert_not_called()

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rag_inactive"
    assert data["target_handler"] == "future_informational_rag"
    assert data["response_code"] == "FUTURE_RAG_NOT_AVAILABLE"
    assert data["safe_to_route"] is False
    assert data["engine_executed"] is False
    assert data["engine_result"] is None


def test_case_h_ambiguous_and_conflicting_inputs():
    """Case H: Ambiguous or conflicting inputs return clarification without engine execution."""
    # H1: Conflicting modality
    resp1 = client.post(
        "/conversation",
        json={"message": "Can I take COP 3330 online and in-person?"},
    )
    assert resp1.status_code == 200
    d1 = resp1.json()
    assert d1["status"] == "clarification"
    assert d1["response_code"] == "INVALID_OR_CONFLICTING_DETAILS"
    assert d1["engine_executed"] is False
    assert d1["safe_to_route"] is False

    # H2: Ambiguous single course workload vs compatibility
    resp2 = client.post(
        "/conversation",
        json={"message": "Is COP 3530 risky?"},
    )
    assert resp2.status_code == 200
    d2 = resp2.json()
    assert d2["status"] == "clarification"
    assert d2["response_code"] == "AMBIGUOUS_REQUEST"
    assert d2["engine_executed"] is False


def test_case_i_unknown_course_and_invalid_profile():
    """Case I: Unknown course or invalid profile calls engine but returns engine_error."""
    # I1: Unknown course in compatibility
    payload_unknown_course = {
        "message": "Can I take COP 9999 and MAP 3305 together?",
        "student_id": "Z24567901",
        "recent_difficulty": 1,
        "satisfied_with_performance": "yes",
        "work_hours": 5.0,
    }
    resp1 = client.post("/conversation", json=payload_unknown_course)
    assert resp1.status_code == 200
    d1 = resp1.json()
    assert d1["status"] == "engine_error"
    assert d1["response_code"] == "ENGINE_EVALUATION_FAILED"
    # Note: engine_executed is True because evaluate_compatibility was called
    assert d1["engine_executed"] is True
    assert d1["engine_result"]["success"] is False
    assert "Some courses were not found" in d1["engine_result"]["error"]

    # I2: Invalid student profile
    payload_invalid_student = {
        "message": "Can I take COP 4331 and MAP 3305 together?",
        "student_id": "Z99999999",
        "recent_difficulty": 1,
        "satisfied_with_performance": "yes",
        "work_hours": 5.0,
    }
    resp2 = client.post("/conversation", json=payload_invalid_student)
    assert resp2.status_code == 200
    d2 = resp2.json()
    assert d2["status"] == "engine_error"
    assert d2["response_code"] == "ENGINE_EVALUATION_FAILED"
    assert d2["engine_executed"] is True
    assert d2["engine_result"]["success"] is False
    assert "profile not found" in d2["engine_result"]["error"]


def test_case_j_engine_exception_handling():
    """Case J: Engine runtime exception is caught, returns engine_error with engine_executed=True."""
    payload = {
        "message": "Can I take COP 4331 and MAP 3305 together?",
        "student_id": "Z24567901",
        "recent_difficulty": 1,
        "satisfied_with_performance": "yes",
        "work_hours": 5.0,
    }

    def failing_engine(*args, **kwargs):
        raise RuntimeError("Simulated internal engine database failure")

    with patch.object(conv_router, "evaluate_compatibility", side_effect=failing_engine):
        resp = client.post("/conversation", json=payload)

    assert resp.status_code == 200
    d = resp.json()
    assert d["status"] == "engine_error"
    assert d["response_code"] == "ENGINE_EXECUTION_ERROR"
    # Contract observation: engine_executed is True even when exception raised!
    assert d["engine_executed"] is True
    assert "Simulated internal engine database failure" in d["response_text"]
    assert d["engine_result"] == {"error": "Simulated internal engine database failure"}
