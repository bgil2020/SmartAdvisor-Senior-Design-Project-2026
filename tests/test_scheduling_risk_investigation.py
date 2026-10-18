"""Corrective regression test suite verifying bounded conversational scheduling stabilization.

Covers:
- >2-section rejection for structured and free-text inputs without silent truncation (Risk A).
- Third section that conflicts when the first pair does not.
- Meeting-time handling: scheduled, verified asynchronous, and unknown/TBA timing (Risk B).
- Synchronous online overlap calculation.
- Contradictory inputs within structured fields and between message and structured context (Risk C).
- Preserving course suffixes and course-section associations.
- Execution-field semantics consistency across handlers (Risk D).
- Alternatives with omitted vs explicitly empty schedule context and valid no-results outcome (Risk E).
- Unsupported preferences disclosure.
- Unknown-time alternative and schedule limitations.

All synthetic fixtures and mocks are explicitly labeled.
"""
from unittest.mock import patch
import pytest
import pandas as pd
from fastapi.testclient import TestClient

from backend.api import app
from backend.section_retriever import load_course_data, get_section_by_crn
from backend.overlap_detector import (
    sections_overlap,
    get_conflict_details,
    has_schedule_information,
)
from backend.meeting_time_normalizer import (
    get_schedule_status,
    is_verified_asynchronous,
    SCHEDULE_STATUS_SCHEDULED,
    SCHEDULE_STATUS_ASYNCHRONOUS,
    SCHEDULE_STATUS_UNKNOWN,
)
from backend.alternative_section_search import find_alternative_sections
import backend.scheduling_service as sched_service
import backend.conversational_router as conv_router

client = TestClient(app)


# ======================================================================
# Risk A: More than Two Sections (Prevent Silent Truncation)
# ======================================================================

def test_risk_a_three_sections_silent_truncation_prevented_structured():
    """Corrective Regression Test for Risk A:
    Verify that requests with >2 structured sections are rejected/clarified with
    EXCESS_SECTIONS_DETECTED, preventing silent truncation and preventing false negative outcomes.

    Setup:
      Sec 1: CRN 20158 (COP 3530C, sect 001, TR 12:30 PM - 01:50 PM)
      Sec 2: CRN 15637 (MAC 2312, sect 002, WF 12:00 PM - 01:50 PM) -> Sec 1 & Sec 2 do NOT overlap.
      Sec 3: CRN 17077 (MAC 2312, sect 006, TR 12:00 PM - 01:50 PM) -> Sec 1 & Sec 3 DO overlap!
    """
    payload = {
        "message": "Do COP 3530C section 001 and MAC 2312 section 002 overlap?",
        "sections": ["20158", "15637", "17077"]
    }
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    # Must reject/clarify rather than silently truncating and falsely reporting NO_SCHEDULE_CONFLICT
    assert data["status"] == "clarification"
    assert data["response_code"] == "EXCESS_SECTIONS_DETECTED"
    assert data["safe_to_route"] is True
    assert data["engine_executed"] is False
    assert "two sections at a time" in data["response_text"]


def test_risk_a_freetext_three_sections_rejected():
    """Verify free-text query referencing 3 sections is rejected without silent truncation,
    specifically where Sec 1 & Sec 2 do not overlap, but Sec 1 & Sec 3 do overlap.
    """
    payload = {
        "message": "Do COP 3530C section 001, MAC 2312 section 002, and MAC 2312 section 006 overlap?"
    }
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "clarification"
    assert data["response_code"] == "EXCESS_SECTIONS_DETECTED"
    assert data["safe_to_route"] is True
    assert data["engine_executed"] is False
    assert "two sections at a time" in data["response_text"]


def test_risk_a_freetext_three_crns_rejected():
    """Verify free-text query with 3 CRNs is rejected with EXCESS_SECTIONS_DETECTED."""
    payload = {
        "message": "Do CRN 20158, CRN 15637, and CRN 17077 conflict?"
    }
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "clarification"
    assert data["response_code"] == "EXCESS_SECTIONS_DETECTED"
    assert data["engine_executed"] is False


# ======================================================================
# Risk B: Unknown versus Asynchronous Meeting Times
# ======================================================================

def test_risk_b_in_person_missing_time_returns_uncertain():
    """Corrective Regression Test for Risk B:
    In-person section with missing/TBA meeting times returns conflict='Unknown',
    and router returns SCHEDULE_UNCERTAIN_TIMING rather than a verified 'no conflict'.
    """
    # Synthetic fixture: In-person section with missing/TBA times
    sec_tba = pd.Series({
        "CRN": "99901",
        "COURSE": "CNT 4403",
        "SECT": "001",
        "BEG TIME": None,
        "END TIME": None,
        "DAYS": None,
        "METHOD": "In-Person",
        "CAMPUS": "Boca Raton",
        "TERM": 202608,
        "ENRL REMN": 10,
    })

    df = load_course_data()
    sec_real = get_section_by_crn(df, "20158")  # TR 12:30 - 1:50 PM

    # 1. sections_overlap returns False because timing cannot be established
    overlap = sections_overlap(sec_tba, sec_real)
    assert overlap is False

    # 2. get_conflict_details returns conflict="Unknown" (insufficient data does not produce verified "No")
    details = get_conflict_details(sec_tba, sec_real)
    assert details["conflict"] == "Unknown"
    assert details["schedule_status"] == "unknown_timing"
    assert "Meeting times are missing, TBA, or unverified" in details["reason"]

    # 3. has_schedule_information accurately flags lack of usable schedule
    assert has_schedule_information(sec_tba) is False

    # 4. Evaluation via scheduling_service returns is_uncertain=True and has_conflict=None
    eval_res = sched_service.evaluate_schedule_conflict(
        courses=pd.concat([df, pd.DataFrame([sec_tba])], ignore_index=True),
        section1_input="99901",
        section2_input="20158"
    )
    assert eval_res["success"] is True
    assert eval_res["has_conflict"] is None
    assert eval_res["is_uncertain"] is True
    assert eval_res["conflict_summary"] == "Unknown"

    # 5. Endpoint returns SCHEDULE_UNCERTAIN_TIMING
    df_combined = pd.concat([df, pd.DataFrame([sec_tba])], ignore_index=True)
    with patch.object(conv_router, "get_course_catalog", return_value=df_combined):
        resp = client.post("/conversation", json={
            "message": "Do CRN 99901 and CRN 20158 overlap?",
            "sections": ["99901", "20158"]
        })
    assert resp.status_code == 200
    d = resp.json()
    assert d["status"] == "engine_executed"
    assert d["response_code"] == "SCHEDULE_UNCERTAIN_TIMING"
    assert d["engine_executed"] is True
    assert d["engine_result"]["has_conflict"] is None
    assert "Cannot verify schedule conflict" in d["response_text"]


def test_risk_b_online_synchronous_undergoes_normal_overlap():
    """Corrective Regression Test for Risk B:
    Synchronous online section with scheduled days and times undergoes normal overlap calculation
    and correctly flags a conflict when meeting times overlap.
    """
    # Synthetic fixture: Synchronous online course meeting T R 12:30 PM - 01:50 PM
    sec_online_sync = pd.Series({
        "CRN": "99902",
        "COURSE": "CIS 4930",
        "SECT": "001",
        "BEG TIME": "12:30 PM",
        "END TIME": "01:50 PM",
        "DAYS": "T  R",
        "METHOD": "Online Live Lecture",
        "CAMPUS": "Online",
        "TERM": 202608,
        "ENRL REMN": 10,
    })

    df = load_course_data()
    sec_real = get_section_by_crn(df, "20158")  # TR 12:30 - 1:50 PM

    # 1. Direct overlap returns True because days and times match
    overlap = sections_overlap(sec_online_sync, sec_real)
    assert overlap is True

    # 2. get_conflict_details returns conflict="Yes" and shared days "T, R"
    details = get_conflict_details(sec_online_sync, sec_real)
    assert details["conflict"] == "Yes"
    assert "T" in details["shared_days"]
    assert "R" in details["shared_days"]

    # 3. has_schedule_information accurately recognizes scheduled synchronous online
    assert has_schedule_information(sec_online_sync) is True

    # 4. Routed evaluation returns SCHEDULE_CONFLICT_FOUND
    df_combined = pd.concat([df, pd.DataFrame([sec_online_sync])], ignore_index=True)
    with patch.object(conv_router, "get_course_catalog", return_value=df_combined):
        resp = client.post("/conversation", json={
            "message": "Do CRN 99902 and CRN 20158 overlap?",
            "sections": ["99902", "20158"]
        })
    assert resp.status_code == 200
    d = resp.json()
    assert d["status"] == "engine_executed"
    assert d["response_code"] == "SCHEDULE_CONFLICT_FOUND"
    assert d["engine_result"]["has_conflict"] is True


def test_risk_b_verified_asynchronous_fixture():
    """Corrective Regression Test for Risk B:
    Explicitly verified asynchronous sections are confirmed non-conflicting without false uncertain flags.
    Clearly labeled synthetic fixture.
    """
    sec_async = pd.Series({
        "CRN": "99903",
        "COURSE": "COP 3530C",
        "SECT": "099",
        "BEG TIME": None,
        "END TIME": None,
        "DAYS": None,
        "METHOD": "Online Asynchronous",
        "CAMPUS": "Distance Learning",
        "TERM": 202608,
        "ENRL REMN": 15,
        "is_asynchronous": True,
    })

    df = load_course_data()
    sec_real = get_section_by_crn(df, "20158")

    # 1. Verification helper flags asynchronous status
    assert is_verified_asynchronous(sec_async) is True
    assert get_schedule_status(sec_async) == SCHEDULE_STATUS_ASYNCHRONOUS

    # 2. Overlap is False
    assert sections_overlap(sec_async, sec_real) is False

    # 3. Details return No conflict with asynchronous note
    details = get_conflict_details(sec_async, sec_real)
    assert details["conflict"] == "No"
    assert details["schedule_status"] == "verified_asynchronous"

    # 4. Router returns NO_SCHEDULE_CONFLICT mentioning verified asynchronous delivery
    df_combined = pd.concat([df, pd.DataFrame([sec_async])], ignore_index=True)
    with patch.object(conv_router, "get_course_catalog", return_value=df_combined):
        resp = client.post("/conversation", json={
            "message": "Do CRN 99903 and CRN 20158 overlap?",
            "sections": ["99903", "20158"]
        })
    assert resp.status_code == 200
    d = resp.json()
    assert d["status"] == "engine_executed"
    assert d["response_code"] == "NO_SCHEDULE_CONFLICT"
    assert d["engine_result"]["has_conflict"] is False
    assert "asynchronous" in d["response_text"].lower()


# ======================================================================
# Risk C: Contradictory Inputs and Context
# ======================================================================

def test_risk_c_contradiction_between_message_and_structured_sections():
    """Corrective Regression Test for Risk C:
    When explicit message references contradict structured sections context,
    return targeted clarification before engine execution.
    """
    payload = {
        # Message mentions COP 3530C (20158) and MAC 2312 section 006 (17077)
        "message": "Do COP 3530C section 001 and MAC 2312 section 006 overlap?",
        # But structured sections supply section 002 (15637)
        "sections": ["20158", "15637"]
    }
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "clarification"
    assert data["response_code"] == "CONTRADICTORY_SECTION_DETAILS"
    assert data["safe_to_route"] is True
    assert data["engine_executed"] is False
    assert "Contradictory section information detected" in data["response_text"]


def test_risk_c_contradictory_crn_and_course_in_dict_rejected():
    """Corrective Regression Test for Risk C:
    CRN is validated against course/section in structured dict, returning explicit contradiction error.
    """
    df = load_course_data()
    contradictory_input = {
        "crn": "20158",
        "course": "MAC 2312",
        "section": "002"
    }
    sec_row, err, amb = sched_service.resolve_section(df, contradictory_input)
    assert sec_row is None
    assert err is not None
    assert "Contradictory section details" in err
    assert "CRN '20158' is course 'COP 3530C'" in err


def test_risk_c_structured_context_fills_missing_message_details():
    """Verify that structured context may fill missing message details without requiring text repetition."""
    payload = {
        "message": "Do these two courses overlap?",
        "sections": ["20158", "15637"]
    }
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "engine_executed"
    assert data["response_code"] == "NO_SCHEDULE_CONFLICT"
    assert data["engine_executed"] is True
    assert data["engine_result"]["section_1"]["crn"] == "20158"
    assert data["engine_result"]["section_2"]["crn"] == "15637"


def test_risk_c_term_mismatch_returns_explicit_error():
    """Demonstrate Risk C: Sections from different terms return an explicit error."""
    df = load_course_data().copy()

    # Add synthetic section for term 202601 to catalog copy
    sec_synthetic_term1 = pd.DataFrame([{
        "CRN": "99911", "COURSE": "COP 3530C", "SECT": "001", "TERM": 202601,
        "BEG TIME": "12:00 PM", "END TIME": "01:00 PM", "DAYS": "M",
        "METHOD": "In-Person", "CAMPUS": "Boca Raton", "ENRL REMN": 5, "TITLE": "Test 1"
    }])
    df_combined = pd.concat([df, sec_synthetic_term1], ignore_index=True)

    # Evaluate conflict between term 202601 section and real term 202608 section (20158)
    res = sched_service.evaluate_schedule_conflict(
        courses=df_combined,
        section1_input="99911",
        section2_input="20158"
    )
    assert res["success"] is False
    assert "Cannot check schedule conflict across different terms" in res["error"]


def test_risk_c_synthetic_multi_term_ambiguity():
    """Verify that resolving course + section across multiple terms without specifying term flags ambiguity."""
    df = load_course_data().copy()
    sec_another_term = pd.DataFrame([{
        "CRN": "99922", "COURSE": "COP 3530C", "SECT": "001", "TERM": 202601,
        "BEG TIME": "02:00 PM", "END TIME": "03:20 PM", "DAYS": "TR",
        "METHOD": "In-Person", "CAMPUS": "Boca Raton", "ENRL REMN": 10, "TITLE": "Test 2"
    }])
    df_multi = pd.concat([df, sec_another_term], ignore_index=True)

    sec_row, err, amb = sched_service.resolve_section(
        df_multi,
        {"course": "COP 3530C", "section": "001"},
        term=None
    )
    assert sec_row is None
    assert amb is True
    assert "Multiple sections matched" in err
    assert "Please specify a term" in err


# ======================================================================
# Risk D: Execution-Field Semantics
# ======================================================================

def test_risk_d_execution_semantics_consistency():
    """Demonstrate Risk D: engine_executed strictly reflects actual engine completion across all handlers."""
    # 1. Compatibility success -> engine_executed is True, safe_to_route is True
    resp_comp = client.post("/conversation", json={
        "message": "Can I take COP 4331 and MAP 3305 together?",
        "student_id": "Z24567901",
        "recent_difficulty": 1,
        "satisfied_with_performance": "yes",
        "work_hours": 5.0,
        "preferred_max_credits": 15.0,
        "recent_courses": ["CDA4240C", "CDA4102", "MAC2313"]
    })
    assert resp_comp.json()["engine_executed"] is True
    assert resp_comp.json()["safe_to_route"] is True

    # 2. Compatibility clarification (missing workload profile in routed handler) -> engine_executed is False, safe_to_route is True
    resp_comp_clar = client.post("/conversation", json={
        "message": "Can I take COP 4331 and MAP 3305 together?",
    })
    assert resp_comp_clar.json()["engine_executed"] is False
    assert resp_comp_clar.json()["safe_to_route"] is True
    assert resp_comp_clar.json()["status"] == "clarification"

    # 3. Scheduling conflict success -> engine_executed is True, safe_to_route is True
    resp_sched = client.post("/conversation", json={
        "message": "Do COP 3530C section 001 and MAC 2312 section 006 overlap?"
    })
    assert resp_sched.json()["engine_executed"] is True
    assert resp_sched.json()["safe_to_route"] is True

    # 4. Scheduling conflict unresolvable section in routed handler -> engine_executed is False, safe_to_route is True
    resp_sched_unresolved = client.post("/conversation", json={
        "message": "Do COP 3530C section 999 and MAC 2312 section 002 overlap?"
    })
    assert resp_sched_unresolved.json()["engine_executed"] is False
    assert resp_sched_unresolved.json()["safe_to_route"] is True
    assert resp_sched_unresolved.json()["status"] == "engine_error"
    assert resp_sched_unresolved.json()["response_code"] == "SECTION_NOT_FOUND"

    # 5. Classifier-level clarification (insufficient prompt details before routing) -> safe_to_route is False
    resp_classifier_clar = client.post("/conversation", json={
        "message": "Do COP 3530C and MAC 2312 overlap?"  # Sections omitted in text
    })
    assert resp_classifier_clar.json()["safe_to_route"] is False
    assert resp_classifier_clar.json()["status"] == "clarification"


# ======================================================================
# Risk E: Resolution, Alternatives, and Limitations
# ======================================================================

def test_risk_e_empty_list_vs_omitted_schedule_context():
    """Demonstrate Risk E: selected_sections=[] executes engine; selected_sections omitted clarifies."""
    # Omitted schedule context
    resp_omitted = client.post("/conversation", json={
        "message": "Find another section of COP 3530C section 001",
        "target_section": "20158"
    })
    assert resp_omitted.json()["status"] == "clarification"
    assert resp_omitted.json()["engine_executed"] is False
    assert resp_omitted.json()["response_code"] == "MISSING_SCHEDULE_CONTEXT"

    # Explicitly empty schedule context
    resp_empty = client.post("/conversation", json={
        "message": "Find another section of COP 3530C section 001",
        "target_section": "20158",
        "selected_sections": []
    })
    assert resp_empty.json()["status"] == "engine_executed"
    assert resp_empty.json()["engine_executed"] is True
    assert resp_empty.json()["response_code"] == "ALTERNATIVE_SECTIONS_FOUND"


def test_risk_e_valid_no_results_outcome():
    """Demonstrate Risk E: A search finding 0 open alternative sections returns engine_executed=True."""
    # Synthetic dataset where all alternative sections have 0 seats
    df = load_course_data().copy()
    mask = (df["COURSE"] == "COP 3530C") & (df["CRN"].astype(str).str.replace(".0", "") != "20158")
    df.loc[mask, "ENRL REMN"] = 0

    alts = find_alternative_sections(
        courses=df,
        conflicted_crn="20158",
        selected_crns=[],
        max_results=3
    )
    assert len(alts) == 0

    res = sched_service.evaluate_alternative_sections(
        courses=df,
        target_section_input="20158",
        selected_sections_input=[]
    )
    assert res["success"] is True
    assert res["count"] == 0
    assert len(res["alternatives"]) == 0


def test_risk_e_unknown_time_in_selected_schedule_discloses_limitation():
    """Verify that when current schedule contains an unknown-time section (e.g. CNT 4403 CRN 18077),
    alternative section search discloses a safe limitation rather than guaranteeing conflict avoidance.
    """
    # CRN 18077 is CNT 4403 section 001 (In-Person with TBA meeting times)
    resp = client.post("/conversation", json={
        "message": "Find another section of COP 3530C section 001",
        "target_section": "20158",
        "selected_sections": ["18077"]  # Enrolled course with TBA times
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "engine_executed"
    assert data["engine_executed"] is True
    assert "Limitation:" in data["response_text"]
    assert "unverified or TBA meeting times" in data["response_text"]
    assert len(data["engine_result"]["limitations"]) > 0


def test_unsupported_preference_disclosed_in_conflict_response():
    """Verify that requested unsupported preferences (such as specific professors or times)
    are disclosed as limitations and not claimed to be satisfied.
    """
    resp = client.post("/conversation", json={
        "message": "Do COP 3530C section 001 and MAC 2312 section 002 overlap? I prefer morning classes with Dr. Smith"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "engine_executed"
    assert "Note: Requested preference" in data["response_text"]
    assert "instructor preference" in data["response_text"] or "time-of-day preference" in data["response_text"]
