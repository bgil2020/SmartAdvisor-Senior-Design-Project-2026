"""Focused diagnostic test suite investigating the 5 specific scheduling risks (A-E).

Tests verify behavior against actual code paths, data structures, and edge cases.
Does not mutate production code or weaken existing tests.
All synthetic fixtures and mocks are explicitly labeled.
"""
import pytest
import pandas as pd
from fastapi.testclient import TestClient

from backend.api import app
from backend.section_retriever import load_course_data, get_section_by_crn
from backend.overlap_detector import sections_overlap, get_conflict_details, has_schedule_information
from backend.alternative_section_search import find_alternative_sections
import backend.scheduling_service as sched_service
import backend.conversational_router as conv_router

client = TestClient(app)


# ======================================================================
# Risk A: More than Two Sections
# ======================================================================

def test_risk_a_three_sections_silent_truncation_false_negative():
    """Demonstrate Risk A: The adapter silently truncates >2 sections to the first 2.
    
    Setup:
      Sec 1: CRN 20158 (COP 3530C, sect 001, TR 12:30 PM - 01:50 PM)
      Sec 2: CRN 15637 (MAC 2312, sect 002, WF 12:00 PM - 01:50 PM) -> Sec 1 & Sec 2 do NOT overlap.
      Sec 3: CRN 17077 (MAC 2312, sect 006, TR 12:00 PM - 01:50 PM) -> Sec 1 & Sec 3 DO overlap!
    
    When three sections are provided:
      The adapter extracts [20158, 15637, 17077].
      It silently slices only the first two: [:2] -> (20158, 15637).
      It evaluates them as NO_SCHEDULE_CONFLICT, producing a false negative (misses the conflict with Sec 3).
    """
    payload = {
        "message": "Do COP 3530C section 001 and MAC 2312 section 002 overlap?",
        "sections": ["20158", "15637", "17077"]
    }
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    
    # Finding: Adapter does NOT reject >2 sections; it silently truncates to [:2]
    assert data["status"] == "engine_executed"
    assert data["response_code"] == "NO_SCHEDULE_CONFLICT"
    assert data["engine_result"]["has_conflict"] is False
    
    # Verify which sections were evaluated: only 1 and 2, 3 was completely ignored
    assert data["engine_result"]["section_1"]["crn"] == "20158"
    assert data["engine_result"]["section_2"]["crn"] == "15637"


# ======================================================================
# Risk B: Unknown versus Asynchronous Meeting Times
# ======================================================================

def test_risk_b_in_person_missing_time_returns_false_no_conflict():
    """Demonstrate Risk B: In-person section with missing/TBA meeting times returns False and 'No' conflict."""
    # Synthetic fixture representing an in-person section with missing/TBA times
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
    sec_real = get_section_by_crn(df, "20158") # TR 12:30 - 1:50 PM
    
    # 1. sections_overlap returns False because start_time is None
    overlap = sections_overlap(sec_tba, sec_real)
    assert overlap is False
    
    # 2. get_conflict_details returns conflict="No", shared_days=""
    details = get_conflict_details(sec_tba, sec_real)
    assert details["conflict"] == "No"
    assert details["shared_days"] == ""
    
    # 3. has_schedule_information accurately flags lack of schedule
    assert has_schedule_information(sec_tba) is False


def test_risk_b_online_synchronous_bypasses_time_overlap():
    """Demonstrate Risk B: Online delivery flag causes overlap detector to return False even if times match."""
    # Synthetic fixture: Online course that has explicit scheduled meeting times identical to sec_real
    sec_online_sync = pd.Series({
        "CRN": "99902",
        "COURSE": "CIS 4930",
        "SECT": "001",
        "BEG TIME": "12:30 PM",
        "END TIME": "01:50 PM",
        "DAYS": "T  R",
        "METHOD": "Online",
        "CAMPUS": "Online",
        "TERM": 202608,
        "ENRL REMN": 10,
    })
    
    df = load_course_data()
    sec_real = get_section_by_crn(df, "20158") # TR 12:30 - 1:50 PM
    
    # Direct overlap returns False solely due to online_section(method) == True
    overlap = sections_overlap(sec_online_sync, sec_real)
    assert overlap is False
    
    details = get_conflict_details(sec_online_sync, sec_real)
    assert details["conflict"] == "No"
    assert details["shared_days"] == ""


# ======================================================================
# Risk C: Contradictory Inputs
# ======================================================================

def test_risk_c_structured_sections_override_message():
    """Demonstrate Risk C: Structured sections override contradictory message text."""
    payload = {
        # Message mentions COP 3530C (20158) and MAC 2312 (17077) which DO overlap
        "message": "Do COP 3530C section 001 and MAC 2312 section 006 overlap?",
        # But structured sections supply non-overlapping sections 20158 and 15637
        "sections": ["20158", "15637"]
    }
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    
    # Finding: Structured sections take precedence, evaluating to NO_SCHEDULE_CONFLICT
    assert data["response_code"] == "NO_SCHEDULE_CONFLICT"
    assert data["engine_result"]["section_2"]["crn"] == "15637"


def test_risk_c_crn_overrides_contradictory_course_in_dict():
    """Demonstrate Risk C: CRN takes precedence over contradictory course/section in structured dict."""
    df = load_course_data()
    # CRN 20158 is actually COP 3530C section 001.
    # Pass contradictory course 'MAC 2312' with CRN 20158.
    contradictory_input = {
        "crn": "20158",
        "course": "MAC 2312",
        "section": "002"
    }
    sec_row, err, amb = sched_service.resolve_section(df, contradictory_input)
    assert err is None
    # CRN resolved to COP 3530C, course 'MAC 2312' was ignored
    assert sec_row["COURSE"] == "COP 3530C"
    assert str(sec_row["CRN"]).replace(".0", "") == "20158"


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
        # Missing workload profile
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
# Risk E: Resolution and Alternatives
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
    # Set all COP 3530C sections other than 20158 to 0 seats
    mask = (df["COURSE"] == "COP 3530C") & (df["CRN"].astype(str).str.replace(".0", "") != "20158")
    df.loc[mask, "ENRL REMN"] = 0
    
    alts = find_alternative_sections(
        courses=df,
        conflicted_crn="20158",
        selected_crns=[],
        max_results=3
    )
    assert len(alts) == 0
    
    # In scheduling_service:
    res = sched_service.evaluate_alternative_sections(
        courses=df,
        target_section_input="20158",
        selected_sections_input=[]
    )
    assert res["success"] is True
    assert res["count"] == 0
    assert len(res["alternatives"]) == 0
