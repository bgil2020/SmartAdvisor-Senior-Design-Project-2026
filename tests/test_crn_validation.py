
from fastapi.testclient import TestClient

from backend.api import app

client = TestClient(app)


def test_invalid_crn_letters():
    response = client.get("/alternatives", params={"crn": "abc123"})

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "string_pattern_mismatch"


def test_missing_crn():
    response = client.get("/alternatives")

    assert response.status_code == 422


def test_nonexistent_numeric_crn():
    response = client.get("/alternatives", params={"crn": "99999999"})

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
