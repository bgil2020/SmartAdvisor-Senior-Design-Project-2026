"""Offline fixture tests for deterministic RAG evidence readiness."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api import app
from backend.course_descriptions.models import write_json
from backend.rag.models import EvidenceChunk
from backend.rag.retriever import LexicalRetriever
from backend.rag.service import answer_information_question


client = TestClient(app)


def fixture_chunk(
    *,
    chunk_id: str,
    category: str,
    course: str,
    locator: str,
    text: str,
    term: str | None = None,
    section: str | None = None,
    source_url: str = "https://example.edu/fixture",
) -> EvidenceChunk:
    """Construct explicitly synthetic evidence; no statement is real source data."""
    return EvidenceChunk(
        chunk_id=chunk_id,
        document_id=f"fixture:{category}:{course}:{term or 'course'}:{section or 'all'}",
        source_version="fixture-v1:fixture-hash",
        record_category=category,
        course_code=course,
        term_id=term,
        term_name="Fixture Term" if term else None,
        section=section,
        title=f"{course} fixture source",
        locator=locator,
        source_url=source_url,
        text=text,
        content_sha256="fixture-content-hash",
        limitations=["Synthetic fixture; not university evidence."],
    )


def description(course: str = "COP4331") -> EvidenceChunk:
    return fixture_chunk(
        chunk_id=f"fixture:{course}:description",
        category="course_description",
        course=course,
        locator="Course Description",
        text="Object-oriented design, Java, patterns, and collaborative software development.",
    )


def syllabus(*, text: str, term: str = "202608", section: str = "001") -> EvidenceChunk:
    return fixture_chunk(
        chunk_id=f"fixture:EEL3111:{term}:{section}:assessment",
        category="syllabus",
        course="EEL3111",
        term=term,
        section=section,
        locator="heading:Course Evaluation Method",
        text=text,
    )


def write_corpus(path: Path, chunks: list[EvidenceChunk]) -> None:
    write_json(path, {"corpus_version": "1.0", "chunks": [item.model_dump() for item in chunks]})


def test_applicable_description_hit_is_ready_and_cited_fallback(monkeypatch):
    monkeypatch.setenv("RAG_GENERATION_MODE", "fallback")
    result = answer_information_question(
        "Which topics are covered by COP4331?",
        course_codes=["COP4331"],
        retriever=LexicalRetriever([description()]),
    )
    assert result.evidence_decision == "ready"
    assert result.generation_source == "source_excerpt_fallback"
    assert result.supporting_source_ids == ["fixture:COP4331:description"]
    assert result.resolved_scope["freshness"] == "unknown"
    assert result.sources[0]["freshness"] == "unknown"


def test_published_prerequisites_require_prerequisite_passage(monkeypatch):
    monkeypatch.setenv("RAG_GENERATION_MODE", "fallback")
    prerequisite = fixture_chunk(
        chunk_id="fixture:COP4331:prerequisites",
        category="course_description",
        course="COP4331",
        locator="Prerequisites",
        text="Fixture prerequisite: a prior programming course.",
    )
    result = answer_information_question(
        "What prerequisites are published for COP4331?",
        course_codes=["COP4331"],
        retriever=LexicalRetriever([description(), prerequisite]),
    )
    assert result.evidence_decision == "ready"
    assert result.supporting_source_ids == ["fixture:COP4331:prerequisites"]


def test_applicable_syllabus_quiz_grading_hit_is_ready(monkeypatch):
    monkeypatch.setenv("RAG_GENERATION_MODE", "fallback")
    result = answer_information_question(
        "How are quizzes graded in EEL3111-001?",
        course_codes=["EEL3111"],
        term_id="202608",
        section="001",
        retriever=LexicalRetriever([syllabus(text="Quizzes are 25 percent; the best five scores count.")]),
    )
    assert result.evidence_decision == "ready"
    assert result.required_source_categories == ["syllabus"]
    assert result.resolved_scope["term_id"] == "202608"
    assert result.resolved_scope["section"] == "001"


def test_wrong_course_term_and_section_are_inapplicable():
    evidence = [
        syllabus(text="Quizzes are worth 25 percent.", term="202608", section="001"),
        description("CDA4102"),
    ]
    retriever = LexicalRetriever(evidence)
    wrong_course = answer_information_question("What topics does COP4331 cover?", course_codes=["COP4331"], retriever=retriever)
    wrong_term = answer_information_question("How are quizzes graded?", course_codes=["EEL3111"], term_id="202701", section="001", retriever=retriever)
    wrong_section = answer_information_question("How are quizzes graded?", course_codes=["EEL3111"], term_id="202608", section="002", retriever=retriever)
    assert wrong_course.evidence_decision == "appropriate_source_absent"
    assert wrong_term.evidence_decision == "appropriate_source_absent"
    assert wrong_section.evidence_decision == "appropriate_source_absent"


def test_description_cannot_substitute_for_syllabus_grading_evidence():
    result = answer_information_question(
        "How are quizzes graded?",
        course_codes=["EEL3111"],
        term_id="202608",
        section="001",
        retriever=LexicalRetriever([description("EEL3111")]),
    )
    assert result.evidence_decision == "appropriate_source_absent"
    assert result.missing_evidence_categories == ["syllabus"]
    assert result.acquisition_eligible is True
    assert result.acquisition_plan and result.acquisition_plan.execute is False


def test_matching_document_without_late_policy_is_content_gap_not_refetch():
    result = answer_information_question(
        "What is the late-quiz policy?",
        course_codes=["EEL3111"],
        term_id="202608",
        section="001",
        retriever=LexicalRetriever([syllabus(text="Quizzes are worth 25 percent and the best five count.")]),
    )
    assert result.evidence_decision == "requested_detail_not_located"
    assert "not found in the checked evidence" in result.answer
    assert result.acquisition_eligible is False
    assert result.acquisition_plan and result.acquisition_plan.evidence_gap == "requested_detail_not_located"


def test_course_description_presence_does_not_support_unmentioned_specific_topic():
    result = answer_information_question(
        "Does COP4331 cover quantum computing?",
        course_codes=["COP4331"],
        retriever=LexicalRetriever([description()]),
    )
    assert result.evidence_decision == "requested_detail_not_located"
    assert result.generation_source == "none"
    assert result.acquisition_eligible is False


def test_missing_empty_and_unreadable_corpora_are_distinguished(tmp_path):
    missing = answer_information_question("What topics does COP4331 cover?", course_codes=["COP4331"], corpus_path=tmp_path / "missing.json")
    empty_path = tmp_path / "empty.json"
    write_corpus(empty_path, [])
    empty = answer_information_question("What topics does COP4331 cover?", course_codes=["COP4331"], corpus_path=empty_path)
    unreadable_path = tmp_path / "unreadable.json"
    unreadable_path.write_text("not-json", encoding="utf-8")
    unreadable = answer_information_question("What topics does COP4331 cover?", course_codes=["COP4331"], corpus_path=unreadable_path)
    assert missing.evidence_decision == "corpus_unavailable"
    assert empty.evidence_decision == "appropriate_source_absent"
    assert unreadable.evidence_decision == "corpus_unavailable"
    assert "does not prove" in missing.limitations[0]


def test_ambiguous_course_and_missing_syllabus_term_require_clarification():
    multi = answer_information_question(
        "Which course topics are covered?",
        course_codes=["COP4331", "CDA4102"],
        retriever=LexicalRetriever([description(), description("CDA4102")]),
    )
    missing_term = answer_information_question(
        "How are quizzes graded in EEL3111-001?",
        course_codes=["EEL3111"],
        section="001",
        retriever=LexicalRetriever([syllabus(text="Quizzes are 25 percent.")]),
    )
    assert multi.evidence_decision == "clarification_required"
    assert missing_term.evidence_decision == "clarification_required"
    assert "term_id" in missing_term.evidence_reason


def test_explicit_and_parsed_identity_conflict_uses_api_clarification():
    response = client.post("/conversation", json={
        "message": "What topics does COP4331 cover?",
        "course_code": "CDA4102",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "clarification"
    assert data["evidence_decision"] == "conflicting_scope"
    assert data["acquisition_eligible"] is False
    assert data["rag_executed"] is True


def test_multi_part_request_reports_partial_support_without_generation():
    result = answer_information_question(
        "What topics does COP4331 cover and how are quizzes graded?",
        course_codes=["COP4331"],
        term_id="202608",
        section="001",
        retriever=LexicalRetriever([description()]),
    )
    assert result.evidence_decision == "partially_supported"
    assert result.generation_source == "none"
    assert result.supporting_source_ids == ["fixture:COP4331:description"]
    assert result.missing_evidence_categories == ["syllabus"]


def test_acquisition_plan_is_data_only_and_executes_no_network():
    with patch("urllib.request.urlopen") as urlopen:
        result = answer_information_question(
            "How are quizzes graded?",
            course_codes=["EEL3111"],
            term_id="202608",
            section="001",
            retriever=LexicalRetriever([]),
        )
    urlopen.assert_not_called()
    assert result.acquisition_plan and result.acquisition_plan.execute is False
    assert "syllabus_browser_collect.py" in result.acquisition_plan.collector_capability


def test_non_rag_scheduling_boundary_has_no_acquisition_plan():
    response = client.post("/conversation", json={"message": "Do my classes overlap?"})
    assert response.status_code == 200
    data = response.json()
    assert data["disposition"] == "clarify"
    assert data["rag_executed"] is False
    assert data["acquisition_plan"] is None


def test_unresolved_conversation_reference_gets_targeted_non_rag_clarification():
    response = client.post("/conversation", json={"message": "What about another course?"})
    assert response.status_code == 200
    data = response.json()
    assert data["disposition"] == "clarify"
    assert "no resolved conversational course reference" in data["response_text"]
    assert data["rag_executed"] is False
    assert data["acquisition_plan"] is None
