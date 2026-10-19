"""Tests for the Conversational Assistant API endpoint (POST /conversation)."""
from fastapi.testclient import TestClient
from backend.api import app

client = TestClient(app)


def test_complete_compatibility_request_executes_engine():
    """Valid message with complete synthetic student profile executes compatibility engine."""
    payload = {
        "message": "Can I take COP 4331 and MAP 3305 together?",
        "student_id": "Z24567901",
        "recent_difficulty": 1,
        "satisfied_with_performance": "yes",
        "work_hours": 5.0,
        "preferred_max_credits": 15.0,
        "recent_courses": ["CDA4240C", "CDA4102", "MAC2313"],
    }
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "engine_executed"
    assert data["engine_executed"] is True
    assert data["safe_to_route"] is True
    assert data["disposition"] == "route_core_engine"
    assert data["target_handler"] == "course_compatibility_engine"
    assert "COP4331" in data["extracted_courses"]
    assert "MAP3305" in data["extracted_courses"]
    assert data["engine_result"] is not None
    assert "assessment" in data["engine_result"]
    assert data["engine_result"]["success"] is True


def test_missing_student_context_does_not_execute_engine():
    """Compatibility query recognized, but missing student context returns clarification without engine execution."""
    payload = {
        "message": "Can I take COP 4331 and MAP 3305 together?",
        # No student_id or workload details provided
    }
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "clarification"
    assert data["engine_executed"] is False
    assert data["safe_to_route"] is True
    assert data["target_handler"] == "course_compatibility_engine"
    assert "student_id" in data["missing_context"]
    assert "work_hours" in data["missing_context"]
    assert data["engine_result"] is None
    assert data["actionable_guidance"] is not None


def test_advisor_escalation_does_not_execute_engine():
    """Requests requiring official university action are escalated without engine execution."""
    payload = {"message": "Can you register me for COP 3530?"}
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "escalation"
    assert data["engine_executed"] is False
    assert data["safe_to_route"] is False
    assert data["disposition"] == "advisor_escalation"
    assert data["target_handler"] == "academic_advisor"


def test_inactive_rag_candidate_does_not_execute_engine():
    """Informational questions are safely flagged as inactive candidate without execution."""
    payload = {"message": "What topics are covered in COP 3530?"}
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rag_inactive"
    assert data["engine_executed"] is False
    assert data["safe_to_route"] is False
    assert data["disposition"] == "future_rag_candidate"


def test_conflicting_details_returns_clarification():
    """Conflicting time or modality constraints return clarification without routing."""
    payload = {"message": "Can I take COP 3330 online and in-person?"}
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "clarification"
    assert data["engine_executed"] is False


def test_schedule_conflict_detection_executes_engine():
    """Scheduling conflict intent executes real overlap detector when valid sections provided."""
    payload = {"message": "Do COP 3530C section 001 and MAC 2312 section 006 overlap?"}
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "engine_executed"
    assert data["engine_executed"] is True
    assert data["response_code"] == "SCHEDULE_CONFLICT_FOUND"
    assert data["target_handler"] == "scheduling_engine"
    assert "COP3530C" in data["extracted_courses"]
    assert "MAC2312" in data["extracted_courses"]
    assert data["engine_result"] is not None
    assert data["engine_result"]["has_conflict"] is True
    assert "T, R" in data["engine_result"]["shared_days"]


def test_schedule_conflict_non_overlapping_pair():
    """Non-overlapping sections execute real engine and return no-conflict outcome."""
    payload = {"message": "Do COP 3530C section 001 and MAC 2312 section 002 overlap?"}
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "engine_executed"
    assert data["engine_executed"] is True
    assert data["response_code"] == "NO_SCHEDULE_CONFLICT"
    assert data["engine_result"]["has_conflict"] is False


def test_alternative_section_search_executes_engine():
    """Alternative section search executes find_alternative_sections with real catalog data."""
    payload = {
        "message": "Find another section of COP 3530C section 001 that fits around my schedule.",
        "target_section": "20158",
        "selected_sections": ["17077"],
    }
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "engine_executed"
    assert data["engine_executed"] is True
    assert data["response_code"] == "ALTERNATIVE_SECTIONS_FOUND"
    assert data["engine_result"]["count"] == 2
    assert len(data["engine_result"]["alternatives"]) == 2


def test_alternative_section_missing_schedule_clarification():
    """Alternative section request missing enrolled schedule context asks for clarification."""
    payload = {
        "message": "Find another section of COP 3530C section 001 that fits around my schedule.",
        "target_section": "20158",
        # selected_sections omitted
    }
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "clarification"
    assert data["engine_executed"] is False
    assert data["response_code"] == "MISSING_SCHEDULE_CONTEXT"
    assert "selected_sections" in data["missing_context"]


def test_online_override_directed_to_structured_ui():
    """Override intent is recognized and directed to the existing structured form."""
    payload = {"message": "Can I take COP 3330 online because I am deployed in the military?"}
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "engine_unavailable"
    assert data["engine_executed"] is False
    assert data["target_handler"] == "online_override_eligibility_engine"
    assert "Online Course Override Evaluator" in data["response_text"]


def test_unsupported_query():
    """Out-of-scope query receives honest unsupported response."""
    payload = {"message": "What grade will I get if I take COP 3530 and CEN 4010?"}
    resp = client.post("/conversation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unsupported"
    assert data["engine_executed"] is False
    assert data["safe_to_route"] is False
    assert data["disposition"] == "unsupported"


def test_empty_message_validation():
    """Empty or whitespace-only message is rejected with 422 or 400."""
    resp = client.post("/conversation", json={"message": ""})
    assert resp.status_code in [400, 422]


def test_invalid_workload_parameters_validation():
    """Out-of-range workload context is rejected with 422 validation error."""
    resp = client.post(
        "/conversation",
        json={"message": "Can I take COP 3330 and CEN 4010?", "recent_difficulty": 10},
    )
    assert resp.status_code == 422
