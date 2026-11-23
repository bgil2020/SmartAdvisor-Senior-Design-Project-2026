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
    assert data["source_scope"] == {"course_code": "EGN3343", "term_id": None, "section": None}
    assert data["acquisition"]["status"] == "no_exact_approved_mapping"
    assert data["acquisition"]["additional_source_acquisitions"] == 0
    assert "Source-grounded" in data["response_text"]
    assert "not enabled" in data["response_text"]
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
    assert data["source_scope"] == {"course_code": "EGN3343", "term_id": None, "section": None}
    assert data["citations"][0]["course_code"] == "EGN3343"
    acquire.assert_called_once_with("EGN3343")
    assert answer.call_args.kwargs["course_codes"] == ["EGN3343"]
    assert answer.call_args.kwargs["term_id"] is None
    assert answer.call_args.kwargs["section"] is None


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
