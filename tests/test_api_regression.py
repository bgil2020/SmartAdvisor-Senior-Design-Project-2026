
from fastapi.testclient import TestClient
from backend.api import app

client = TestClient(app)


def test_home_endpoint():
    response = client.get("/")
    assert response.status_code == 200


def test_courses_endpoint():
    response = client.get("/courses")
    assert response.status_code == 200
    assert "courses" in response.json()


def test_sections_endpoint():
    response = client.get("/sections")
    assert response.status_code == 200
    assert "sections" in response.json()


def test_alternatives_missing_crn():
    response = client.get("/alternatives")
    assert response.status_code == 422


def test_alternatives_invalid_crn():
    response = client.get("/alternatives", params={"crn": "abc123"})
    assert response.status_code == 422


def test_alternatives_empty_crn():
    response = client.get("/alternatives", params={"crn": ""})
    assert response.status_code == 422


def test_alternatives_nonexistent_crn():
    response = client.get("/alternatives", params={"crn": "99999999"})
    assert response.status_code == 404


def test_unknown_endpoint():
    response = client.get("/endpoint-that-does-not-exist")
    assert response.status_code == 404
