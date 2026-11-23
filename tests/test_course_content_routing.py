"""Regression coverage for explicit course-content questions through /conversation."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import backend.conversational_router as conversation_router
from backend.api import app


client = TestClient(app)
MESSAGE = "What material is covered in EGN3343?"
EGN_SECTION = {"course": "EGN3343", "section": "001", "crn": "16828", "term": "202608"}
THREE_COURSE_SELECTION = [
    {"course": "EEL4652C", "section": "001", "crn": "19425", "term": "202608"},
    EGN_SECTION,
    {"course": "COP3035C", "section": "004", "crn": "20155", "term": "202608"},
]


@pytest.mark.parametrize("selected_sections", [None, [EGN_SECTION], THREE_COURSE_SELECTION])
def test_exact_content_message_targets_egn3343_independent_of_selection(monkeypatch, selected_sections):
    """An explicit course in the message owns source scope, not the shared selection."""
    monkeypatch.setenv("CONVERSATIONAL_PARSER_MODE", "deterministic")
    monkeypatch.setenv("CATALOG_ACQUISITION_ENABLED", "false")
    payload = {"message": MESSAGE}
    if selected_sections is not None:
        payload["selected_sections"] = selected_sections

    unavailable = {
        "status": "no_exact_approved_mapping",
        "record": None,
        "request_count": 0,
        "cleanup": "not_started",
    }
    with patch.object(conversation_router, "acquire_exact_course_description", return_value=unavailable) as acquire:
        response = client.post("/conversation", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_relevant_evidence"
    assert data["response_code"] == "RAG_NO_RELEVANT_EVIDENCE"
    assert data["disposition"] == "future_rag_candidate"
    assert data["extracted_courses"] == ["EGN3343"]
    expected_scope = (
        {"course_code": "EGN3343", "term_id": "202608", "section": "001"}
        if selected_sections
        else {"course_code": "EGN3343", "term_id": None, "section": None}
    )
    assert data["source_scope"] == expected_scope
    assert data["acquisition"]["status"] == "no_exact_approved_mapping"
    assert data["acquisition"]["additional_source_acquisitions"] == 0
    assert data["response_text"] == "No approved course-information source is configured for EGN3343."
    assert "will not invent course content" in data["actionable_guidance"]
    acquire.assert_called_once_with("EGN3343")


@pytest.mark.parametrize(
    "message",
    [
        "What material is covered in EGN3343?",
        "What topics are covered in EGN 3343?",
        "What does EGN 3343 cover?",
        "What will I learn in EGN 3343?",
        "What is taught in EGN 3343?",
    ],
)
def test_course_content_paraphrases_reach_grounded_generation_path(monkeypatch, message):
    """All supported paraphrases reach exact acquisition and the RAG answer service."""
    monkeypatch.setenv("CONVERSATIONAL_PARSER_MODE", "deterministic")
    monkeypatch.setenv("CATALOG_ACQUISITION_ENABLED", "false")
    record = {"record_id": "fixture:egn3343", "course_code": "EGN3343", "record_category": "course_description"}
    acquired = {
        "status": "acquired",
        "record": record,
        "request_count": 1,
        "cleanup": "complete",
    }
    rag_result = SimpleNamespace(
        status="answered",
        answer="The validated fixture lists engineering economy topics. [fixture:egn3343:description]",
        sources=[{
            "source_id": "fixture:egn3343:description",
            "document_id": "fixture:egn3343",
            "course_code": "EGN3343",
            "title": "Synthetic EGN3343 course description",
            "url": "https://example.edu/fixtures/egn3343",
            "locator": "field:description",
        }],
        generation_source="source_excerpt_fallback",
        model_id=None,
        generation_fallback_used=True,
        generation_fallback_reason="offline fixture provider",
        retrieved_evidence=[{"chunk_id": "fixture:egn3343:description"}],
        limitations=["Offline synthetic fixture."],
    )

    with (
        patch.object(conversation_router, "acquire_exact_course_description", return_value=acquired) as acquire,
        patch.object(conversation_router, "answer_information_records", return_value=rag_result) as answer,
    ):
        response = client.post(
            "/conversation",
            json={"message": message, "selected_sections": THREE_COURSE_SELECTION},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "grounded_answer"
    assert data["extracted_courses"] == ["EGN3343"]
    assert data["source_scope"] == {"course_code": "EGN3343", "term_id": "202608", "section": "001"}
    assert data["citations"][0]["course_code"] == "EGN3343"
    acquire.assert_called_once_with("EGN3343")
    assert answer.call_args.kwargs["course_codes"] == ["EGN3343"]
    assert answer.call_args.kwargs["term_id"] == "202608"
    assert answer.call_args.kwargs["section"] == "001"


def test_syllabus_content_question_asks_for_missing_term_and_section(monkeypatch):
    """Syllabus-specific content does not invent a mapping when its scope is incomplete."""
    monkeypatch.setenv("CONVERSATIONAL_PARSER_MODE", "deterministic")
    response = client.post(
        "/conversation",
        json={"message": "What grading material is covered in EGN3343?"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "clarification"
    assert data["response_code"] == "SOURCE_SCOPE_INCOMPLETE"
    assert data["source_scope"] == {"course_code": "EGN3343", "term_id": None, "section": None}
    assert data["missing_context"] == ["term_id", "section"]
    assert "term and section" in data["response_text"]


def test_selected_section_supplies_exact_syllabus_scope(monkeypatch):
    """An exact selected section supplies source identity without another clarification."""
    monkeypatch.setenv("CONVERSATIONAL_PARSER_MODE", "deterministic")
    monkeypatch.setenv("SYLLABUS_ACQUISITION_ENABLED", "false")
    monkeypatch.setenv("SESSION_EVIDENCE_SIGNING_KEY", "offline-test-signing-key-with-sufficient-length")

    response = client.post(
        "/conversation",
        json={
            "message": "What grading information is in the syllabus for CAP 4773?",
            "term": 202608,
            "selected_sections": [
                {"course": "CAP 4773", "section": "001", "crn": "18637", "term": 202608},
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["response_code"] == "RAG_NO_RELEVANT_EVIDENCE"
    assert data["source_scope"] == {"course_code": "CAP4773", "term_id": "202608", "section": "001"}
    assert data["missing_context"] == []


def test_selected_section_completes_retained_course_context(monkeypatch):
    """A prior incomplete response cannot mask the exact current planner identity."""
    monkeypatch.setenv("CONVERSATIONAL_PARSER_MODE", "deterministic")
    monkeypatch.setenv("SYLLABUS_ACQUISITION_ENABLED", "false")
    monkeypatch.setenv("SESSION_EVIDENCE_SIGNING_KEY", "offline-test-signing-key-with-sufficient-length")

    response = client.post(
        "/conversation",
        json={
            "message": "What grading information is in the syllabus for CAP 4773?",
            "session_context": {"course_code": "CAP4773", "term_id": None, "section": None},
            "selected_sections": [
                {"course": "CAP 4773", "section": "001", "crn": "18637", "term": 202608},
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["source_scope"] == {"course_code": "CAP4773", "term_id": "202608", "section": "001"}
    assert data["response_code"] != "SOURCE_SCOPE_INCOMPLETE"


def test_exact_live_message_uses_selected_scope_through_generation_path(monkeypatch):
    monkeypatch.setenv("CONVERSATIONAL_PARSER_MODE", "deterministic")
    monkeypatch.setenv("SESSION_EVIDENCE_SIGNING_KEY", "offline-test-signing-key-with-sufficient-length")
    record = {
        "record_id": "fixture:cap4773:202608:001",
        "record_category": "syllabus",
        "course_code": "CAP4773",
        "term_scope": {"term_id": "202608"},
        "section_scope": {"section": "001"},
    }
    acquisition = {"status": "acquired", "record": record, "request_count": 1, "cleanup": "complete"}
    rag_result = SimpleNamespace(
        status="answered",
        answer="The validated offline fixture contains a grading scale.",
        sources=[{
            "source_id": "fixture:cap4773:grading",
            "document_id": "fixture:cap4773:202608:001",
            "course_code": "CAP4773",
            "term_id": "202608",
            "section": "001",
            "title": "Synthetic CAP 4773 syllabus",
            "url": "https://example.edu/fixtures/cap4773",
            "locator": "section:grading",
        }],
        generation_source="source_excerpt_fallback",
        model_id=None,
        generation_fallback_used=True,
        generation_fallback_reason="offline fake provider",
        retrieved_evidence=[{"chunk_id": "fixture:cap4773:grading"}],
        limitations=["Offline synthetic fixture."],
    )

    with (
        patch.object(conversation_router, "acquire_exact_syllabus", return_value=acquisition) as acquire,
        patch.object(conversation_router, "answer_information_records", return_value=rag_result) as answer,
    ):
        response = client.post(
            "/conversation",
            json={
                "message": "What grading information is in the syllabus for CAP 4773?",
                "selected_sections": [
                    {"course": "CAP 4773", "section": "001", "crn": "18637", "term": 202608},
                ],
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "grounded_answer"
    assert data["source_scope"] == {"course_code": "CAP4773", "term_id": "202608", "section": "001"}
    assert data["citations"][0]["course_code"] == "CAP4773"
    acquire.assert_called_once_with("CAP4773", "202608", "001")
    assert answer.call_args.kwargs["term_id"] == "202608"
    assert answer.call_args.kwargs["section"] == "001"


def test_automatic_discovery_routes_selected_course_topics_to_exact_syllabus(monkeypatch):
    monkeypatch.setenv("CONVERSATIONAL_PARSER_MODE", "deterministic")
    monkeypatch.setenv("SYLLABUS_ACQUISITION_ENABLED", "true")
    monkeypatch.setenv("SYLLABUS_AUTO_DISCOVERY_ENABLED", "true")
    monkeypatch.setenv("SESSION_EVIDENCE_SIGNING_KEY", "offline-test-signing-key-with-sufficient-length")
    record = {
        "record_id": "fixture:map3305:202608:003",
        "record_category": "syllabus",
        "course_code": "MAP3305",
        "term_scope": {"term_id": "202608"},
        "section_scope": {"section": "003"},
    }
    acquisition = {
        "status": "acquired", "record": record, "request_count": 2,
        "application_acquisition_attempts": 1,
        "cleanup": "completed", "source_discovery": {"status": "exact_source_selected"},
    }
    rag_result = SimpleNamespace(
        status="answered",
        answer="The exact offline syllabus fixture lists the covered topics.",
        sources=[{
            "source_id": "fixture:map3305:topics", "document_id": record["record_id"],
            "course_code": "MAP3305", "term_id": "202608", "section": "003",
            "title": "Synthetic MAP 3305 syllabus", "url": "https://example.edu/fixture",
            "locator": "heading:Course Description",
        }],
        generation_source="source_excerpt_fallback", model_id=None,
        generation_fallback_used=True, generation_fallback_reason="offline fixture",
        retrieved_evidence=[{"chunk_id": "fixture:map3305:topics"}], limitations=["Offline fixture."],
    )

    with (
        patch.object(conversation_router, "acquire_exact_syllabus", return_value=acquisition) as acquire_syllabus,
        patch.object(conversation_router, "acquire_exact_course_description") as acquire_catalog,
        patch.object(conversation_router, "answer_information_records", return_value=rag_result),
    ):
        response = client.post(
            "/conversation",
            json={
                "message": "What topics are covered in MAP 3305?",
                "selected_sections": [{"course": "MAP3305", "section": "003", "term": "202608", "crn": "16355"}],
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "grounded_answer"
    assert data["source_scope"] == {"course_code": "MAP3305", "term_id": "202608", "section": "003"}
    assert data["acquisition"]["source_category"] == "syllabus"
    assert data["acquisition"]["additional_source_acquisitions"] == 1
    acquire_syllabus.assert_called_once_with("MAP3305", "202608", "003")
    acquire_catalog.assert_not_called()


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("discovery_error", "library search could not complete"),
        ("discovery_response_budget_exhausted", "bounded response limit"),
        ("source_access_denied", "anonymously accessible exact match"),
        ("source_rate_limited", "rate-limited"),
    ],
)
def test_discovery_failures_are_reported_without_raw_browser_details(monkeypatch, status, expected):
    monkeypatch.setenv("CONVERSATIONAL_PARSER_MODE", "deterministic")
    monkeypatch.setenv("SYLLABUS_ACQUISITION_ENABLED", "true")
    monkeypatch.setenv("SYLLABUS_AUTO_DISCOVERY_ENABLED", "true")
    monkeypatch.setenv("SESSION_EVIDENCE_SIGNING_KEY", "offline-test-signing-key-with-sufficient-length")
    failure = {
        "status": status, "record": None, "request_count": 1,
        "application_acquisition_attempts": 1, "error_type": "SensitiveBrowserDetail",
    }

    with patch.object(conversation_router, "acquire_exact_syllabus", return_value=failure):
        response = client.post(
            "/conversation",
            json={
                "message": "What topics are covered in MAP 3305?",
                "selected_sections": [{"course": "MAP3305", "section": "003", "term": "202608", "crn": "16355"}],
            },
        )

    data = response.json()
    assert data["status"] == "acquisition_failed"
    assert expected in data["response_text"]
    assert "SensitiveBrowserDetail" not in data["response_text"]


def test_explicit_course_selects_its_section_from_multi_course_schedule(monkeypatch):
    """Explicit course targeting remains authoritative in a larger selected schedule."""
    monkeypatch.setenv("CONVERSATIONAL_PARSER_MODE", "deterministic")
    monkeypatch.setenv("SYLLABUS_ACQUISITION_ENABLED", "false")
    monkeypatch.setenv("SESSION_EVIDENCE_SIGNING_KEY", "offline-test-signing-key-with-sufficient-length")

    response = client.post(
        "/conversation",
        json={
            "message": "What grading information is in the syllabus for EGN 3343?",
            "selected_sections": THREE_COURSE_SELECTION,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["source_scope"] == {"course_code": "EGN3343", "term_id": "202608", "section": "001"}
    assert data["missing_context"] == []


def test_single_selected_section_can_supply_implicit_course(monkeypatch):
    """A singular planner selection resolves a course-content question without a code."""
    monkeypatch.setenv("CONVERSATIONAL_PARSER_MODE", "deterministic")
    monkeypatch.setenv("SYLLABUS_ACQUISITION_ENABLED", "false")
    monkeypatch.setenv("SESSION_EVIDENCE_SIGNING_KEY", "offline-test-signing-key-with-sufficient-length")

    response = client.post(
        "/conversation",
        json={
            "message": "What grading information is in the syllabus?",
            "selected_sections": [{"course": "CAP4773", "section": "001", "term": "202608", "crn": "18637"}],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["source_scope"] == {"course_code": "CAP4773", "term_id": "202608", "section": "001"}
    assert data["extracted_courses"] == ["CAP4773"]


def test_multiple_selected_sections_do_not_guess_an_implicit_course(monkeypatch):
    monkeypatch.setenv("CONVERSATIONAL_PARSER_MODE", "deterministic")
    response = client.post(
        "/conversation",
        json={"message": "What grading information is in the syllabus?", "selected_sections": THREE_COURSE_SELECTION},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "clarification"
    assert data["response_code"] == "SOURCE_SCOPE_AMBIGUOUS"
