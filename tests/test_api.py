from fastapi.testclient import TestClient

from backend.api import app


client = TestClient(app)


def test_get_all_courses():
    response = client.get("/courses")
    assert response.status_code == 200

    data = response.json()

    assert "count" in data
    assert "courses" in data
    assert data["count"] > 0


def test_get_cap_4773_sections():
    response = client.get(
        "/sections",
        params={"course": "CAP 4773"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] > 0

    for section in data["sections"]:
        assert section["COURSE"].upper() == "CAP 4773"


def test_get_section_by_crn():
    response = client.get(
        "/sections",
        params={"crn": "19417"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 1
    assert str(data["sections"][0]["CRN"]) == "19417"


def test_department_filter():
    response = client.get(
        "/courses",
        params={"department": "CAP"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] > 0

    for course in data["courses"]:
        assert course["COURSE"].upper().startswith("CAP")


def test_online_modality_filter():
    response = client.get(
        "/courses",
        params={"modality": "online"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] > 0
    assert data["filters"]["modality"] == "online"