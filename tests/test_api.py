from fastapi.testclient import TestClient

from backend.api import app


client = TestClient(app)


def test_runtime_config_uses_bounded_conversation_timeout(monkeypatch):
    monkeypatch.setenv("CONVERSATION_REQUEST_TIMEOUT_SECONDS", "75")
    assert client.get("/runtime-config").json() == {"conversation_request_timeout_ms": 75000}

    monkeypatch.setenv("CONVERSATION_REQUEST_TIMEOUT_SECONDS", "999")
    assert client.get("/runtime-config").json() == {"conversation_request_timeout_ms": 120000}

    monkeypatch.setenv("CONVERSATION_REQUEST_TIMEOUT_SECONDS", "invalid")
    assert client.get("/runtime-config").json() == {"conversation_request_timeout_ms": 75000}


def test_get_all_courses():
    response = client.get("/courses")
    assert response.status_code == 200

    data = response.json()

    assert "count" in data
    assert "courses" in data
    assert data["count"] > 0


def test_courses_report_only_enabled_exact_approved_information_sources(monkeypatch):
    monkeypatch.setenv("CATALOG_ACQUISITION_ENABLED", "true")
    monkeypatch.setenv("SYLLABUS_ACQUISITION_ENABLED", "true")
    response = client.get("/courses")
    assert response.status_code == 200
    records = response.json()["courses"]
    cap = next(record for record in records if record["COURSE"].replace(" ", "") == "CAP4773")
    map_course = next(record for record in records if record["COURSE"].replace(" ", "") == "MAP3305")
    assert cap["INFORMATION_SOURCE_MAPPINGS"] == ["course_description", "syllabus"]
    assert cap["INFORMATION_SOURCES"] == ["course_description", "syllabus"]
    assert map_course["INFORMATION_SOURCE_MAPPINGS"] == []
    assert map_course["INFORMATION_SOURCES"] == []


def test_courses_do_not_advertise_disabled_source_workflows(monkeypatch):
    monkeypatch.setenv("CATALOG_ACQUISITION_ENABLED", "false")
    monkeypatch.setenv("SYLLABUS_ACQUISITION_ENABLED", "true")
    records = client.get("/courses").json()["courses"]
    cap = next(record for record in records if record["COURSE"].replace(" ", "") == "CAP4773")
    assert cap["INFORMATION_SOURCE_MAPPINGS"] == ["course_description", "syllabus"]
    assert cap["INFORMATION_SOURCES"] == ["syllabus"]


def test_courses_advertise_opt_in_syllabus_discovery_without_claiming_static_mapping(monkeypatch):
    monkeypatch.setenv("CATALOG_ACQUISITION_ENABLED", "false")
    monkeypatch.setenv("SYLLABUS_ACQUISITION_ENABLED", "true")
    monkeypatch.setenv("SYLLABUS_AUTO_DISCOVERY_ENABLED", "true")

    records = client.get("/courses").json()["courses"]
    map_course = next(record for record in records if record["COURSE"].replace(" ", "") == "MAP3305")

    assert map_course["INFORMATION_SOURCE_MAPPINGS"] == []
    assert map_course["INFORMATION_SOURCES"] == ["syllabus"]
    assert map_course["INFORMATION_SOURCE_DISCOVERY"] == ["syllabus"]


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
