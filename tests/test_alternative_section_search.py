from fastapi.testclient import TestClient

from backend.api import app


client = TestClient(app)


def test_alternatives_endpoint():
    response = client.get(
        "/alternatives",
        params={
            "crn": "19417",
            "selected_crns": "20142,20820,20825",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["requested_crn"] == "19417"
    assert data["count"] <= 3
    assert isinstance(data["alternatives"], list)


def test_alternative_same_course():
    response = client.get(
        "/alternatives",
        params={
            "crn": "19417",
            "selected_crns": "20142,20820,20825",
        },
    )

    data = response.json()

    for section in data["alternatives"]:
        assert section["COURSE"] == "CAP 4773"


def test_original_crn_not_returned():
    response = client.get(
        "/alternatives",
        params={
            "crn": "19417",
            "selected_crns": "20142,20820,20825",
        },
    )

    data = response.json()

    returned_crns = [
        str(section["CRN"]).replace(".0", "")
        for section in data["alternatives"]
    ]

    assert "19417" not in returned_crns


def test_maximum_three_alternatives():
    response = client.get(
        "/alternatives",
        params={
            "crn": "19417",
            "selected_crns": "20142,20820,20825",
        },
    )

    data = response.json()

    assert len(data["alternatives"]) <= 3


def test_invalid_crn():
    response = client.get(
        "/alternatives",
        params={
            "crn": "999999",
            "selected_crns": "20142,20820,20825",
        },
    )

    assert response.status_code == 404

    data = response.json()

    assert data["detail"] == "CRN 999999 was not found."