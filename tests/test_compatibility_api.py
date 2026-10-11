from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.api import app


client = TestClient(app)

VALID_PAYLOAD = {
    "student_id": "Z24567901",
    "proposed_courses": [
        "COP4331",
        "MAP3305",
        "CDA4630",
        "CEN4214",
    ],
    "recent_difficulty": 1,
    "satisfied_with_performance": "yes",
    "work_hours": 5.0,
    "preferred_max_credits": 15.0,
    "recent_courses": [
        "CDA4240C",
        "CDA4102",
        "EEL3502",
        "MAC2313",
    ],
}


def test_valid_student_and_courses():
    response = client.post("/compatibility", json=VALID_PAYLOAD)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["student_id"] == "Z24567901"
    assert data["student_name"] == "Evie Woods"
    assert data["major"] == "Electrical Engineering"
    assert len(data["proposed_courses"]) == 4
    assert data["proposed_credits"] > 0
    assert "assessment" in data
    assert "recommendations" in data
    assert "matched_course_combinations" in data


def test_unknown_student_profile():
    payload = VALID_PAYLOAD.copy()
    payload["student_id"] = "Z99999999"

    response = client.post("/compatibility", json=payload)
    assert response.status_code == 400

    data = response.json()
    assert "detail" in data
    assert data["detail"]["success"] is False
    assert "Synthetic student profile not found" in data["detail"]["error"]


def test_unknown_proposed_courses():
    payload = VALID_PAYLOAD.copy()
    payload["proposed_courses"] = ["NONEXIST999"]

    response = client.post("/compatibility", json=payload)
    assert response.status_code == 400

    data = response.json()
    assert "detail" in data
    assert data["detail"]["success"] is False
    assert "NONEXIST999" in data["detail"]["missing_proposed_courses"]


def test_unknown_recent_courses():
    payload = VALID_PAYLOAD.copy()
    payload["recent_courses"] = ["NONEXIST888"]

    response = client.post("/compatibility", json=payload)
    assert response.status_code == 400

    data = response.json()
    assert "detail" in data
    assert data["detail"]["success"] is False
    assert "NONEXIST888" in data["detail"]["missing_recent_courses"]


def test_empty_proposed_courses():
    payload = VALID_PAYLOAD.copy()
    payload["proposed_courses"] = []

    response = client.post("/compatibility", json=payload)
    # Pydantic schema validation error (min_length=1)
    assert response.status_code == 422


def test_missing_required_fields():
    # student_id missing
    payload = {
        "proposed_courses": ["COP4331"],
        "recent_difficulty": 3,
        "satisfied_with_performance": "yes",
        "work_hours": 10.0,
    }
    response = client.post("/compatibility", json=payload)
    assert response.status_code == 422


def test_invalid_difficulty():
    # difficulty out of range (ge=1, le=5)
    payload_low = VALID_PAYLOAD.copy()
    payload_low["recent_difficulty"] = 0
    response_low = client.post("/compatibility", json=payload_low)
    assert response_low.status_code == 422

    payload_high = VALID_PAYLOAD.copy()
    payload_high["recent_difficulty"] = 6
    response_high = client.post("/compatibility", json=payload_high)
    assert response_high.status_code == 422


def test_invalid_satisfaction():
    # satisfaction not in ['yes', 'mostly', 'no']
    payload = VALID_PAYLOAD.copy()
    payload["satisfied_with_performance"] = "uncertain"

    response = client.post("/compatibility", json=payload)
    assert response.status_code == 422


def test_invalid_work_hours():
    # work hours negative or over 80
    payload_neg = VALID_PAYLOAD.copy()
    payload_neg["work_hours"] = -5.0
    response_neg = client.post("/compatibility", json=payload_neg)
    assert response_neg.status_code == 422

    payload_high = VALID_PAYLOAD.copy()
    payload_high["work_hours"] = 85.0
    response_high = client.post("/compatibility", json=payload_high)
    assert response_high.status_code == 422


def test_invalid_credit_preference():
    # preferred_max_credits out of range (ge=1, le=30)
    payload_low = VALID_PAYLOAD.copy()
    payload_low["preferred_max_credits"] = 0
    response_low = client.post("/compatibility", json=payload_low)
    assert response_low.status_code == 422

    payload_high = VALID_PAYLOAD.copy()
    payload_high["preferred_max_credits"] = 35
    response_high = client.post("/compatibility", json=payload_high)
    assert response_high.status_code == 422


def test_missing_compatibility_data():
    with patch(
        "backend.compatibility_engine.load_profiles",
        side_effect=FileNotFoundError("Synthetic Profiles.xlsx missing"),
    ):
        response = client.post("/compatibility", json=VALID_PAYLOAD)
        assert response.status_code == 500
        assert "Compatibility data unavailable" in response.json()["detail"]


def test_cors_preflight_post():
    response = client.options(
        "/compatibility",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert "POST" in response.headers.get("access-control-allow-methods", "")


def test_existing_endpoints_regression():
    # Ensure existing GET endpoints continue to work
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert res_root.json()["application"] == "SmartAdvisor"

    res_courses = client.get("/courses", params={"department": "CAP"})
    assert res_courses.status_code == 200
    assert res_courses.json()["count"] > 0

    res_sections = client.get("/sections", params={"crn": "19417"})
    assert res_sections.status_code == 200
    assert res_sections.json()["count"] == 1

    res_alt = client.get(
        "/alternatives",
        params={"crn": "19417", "selected_crns": "15162"},
    )
    assert res_alt.status_code == 200
    assert res_alt.json()["count"] > 0
