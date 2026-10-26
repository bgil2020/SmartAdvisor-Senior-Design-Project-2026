"""Focused acceptance tests for guarded conversational explanations."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api import app
import backend.conversational_router as conv_router
from backend.app.conversational.explanation_contract import (
    BaseExplanationProvider,
    DEFAULT_EXPLANATION_DISCLAIMER,
    EXPLANATION_CONTRACT_VERSION,
    ExplanationProposal,
    render_explanation,
)


client = TestClient(app)


class AcceptingProvider(BaseExplanationProvider):
    def __init__(self):
        self.payload = None

    def propose(self, payload):
        self.payload = payload
        return ExplanationProposal(
            template_id=payload.expected_template,
            evidence_references=payload.required_evidence_references,
            limitation_codes=payload.required_limitation_codes,
        )


class RaisingProvider(BaseExplanationProvider):
    def propose(self, payload):
        raise ConnectionError("provider unavailable with sensitive detail")


class StaticProvider(BaseExplanationProvider):
    def __init__(self, proposal):
        self.proposal = proposal

    def propose(self, payload):
        return self.proposal


class WrongTemplateProvider(BaseExplanationProvider):
    def propose(self, payload):
        return ExplanationProposal(
            template_id="schedule_unknown",
            evidence_references=payload.required_evidence_references,
            limitation_codes=payload.required_limitation_codes,
        )


class MissingLimitationProvider(BaseExplanationProvider):
    def propose(self, payload):
        return ExplanationProposal(
            template_id=payload.expected_template,
            evidence_references=payload.required_evidence_references,
            limitation_codes=["preliminary_only"],
        )


def compatibility_result(provider=None):
    return render_explanation(
        response_code="COMPATIBILITY_EVALUATION_COMPLETE",
        target_handler="course_compatibility_engine",
        current_text="legacy text",
        extracted_courses=["COP4331", "MAP3305"],
        engine_result={
            "success": True,
            "student_id": "Z00000001",
            "student_name": "Private Student",
            "academic_history": ["PRIVATE101"],
            "assessment": "Manageable with caution",
            "proposed_courses": ["COP4331", "MAP3305"],
            "proposed_credits": 6,
            "repeat_course_warning": "COP4331 appears in recent coursework.",
            "recommendations": ["Discuss the repeat with an advisor."],
            "data_warnings": ["One workload estimate is incomplete."],
        },
        provider=provider,
    )


def test_compatibility_uses_authoritative_facts_warnings_and_safe_disclaimer():
    result = compatibility_result()

    assert result.explanation_source == "deterministic"
    assert "Manageable with caution" in result.response_text
    assert "COP4331 appears in recent coursework" in result.response_text
    assert "One workload estimate is incomplete" in result.response_text
    assert result.disclaimer == DEFAULT_EXPLANATION_DISCLAIMER
    disclaimer = result.disclaimer.lower()
    for boundary in ("approve", "register", "waive prerequisites", "guarantee graduation", "official university policy"):
        assert boundary in disclaimer


def test_provider_receives_only_approved_derived_evidence_and_can_select_valid_contract():
    provider = AcceptingProvider()
    result = compatibility_result(provider)

    assert result.explanation_source == "provider_structured"
    assert result.explanation_fallback_used is False
    assert result.contract_version == EXPLANATION_CONTRACT_VERSION
    serialized = provider.payload.model_dump_json()
    for private_value in ("Z00000001", "Private Student", "PRIVATE101", "student_id", "student_name", "academic_history"):
        assert private_value not in serialized
    assert set(result.evidence_references) == set(provider.payload.required_evidence_references)


@pytest.mark.parametrize(
    "provider,reason_type",
    [
        (RaisingProvider(), "ConnectionError"),
        (WrongTemplateProvider(), "ValueError"),
        (MissingLimitationProvider(), "ValueError"),
        (StaticProvider({"unexpected": "shape"}), "ValidationError"),
        (
            StaticProvider(
                {
                    "contract_version": "1.0",
                    "template_id": "compatibility_result",
                    "evidence_references": ["response.code", "engine.invented_policy"],
                    "limitation_codes": ["preliminary_only", "official_advising_required"],
                }
            ),
            "ValueError",
        ),
        (
            StaticProvider(
                {
                    "contract_version": "1.0",
                    "template_id": "compatibility_result",
                    "evidence_references": ["response.code", "engine.assessment"],
                    "limitation_codes": ["preliminary_only", "official_advising_required"],
                    "facts": {"assessment": "Officially approved"},
                }
            ),
            "ValidationError",
        ),
        (
            StaticProvider(
                {
                    "contract_version": "1.0",
                    "template_id": "compatibility_result",
                    "evidence_references": ["response.code", "engine.assessment"],
                    "limitation_codes": ["preliminary_only", "official_advising_required"],
                    "official_claim": "The university guarantees graduation.",
                }
            ),
            "ValidationError",
        ),
    ],
)
def test_unsafe_invalid_or_unavailable_provider_falls_back_without_changing_facts(provider, reason_type):
    result = compatibility_result(provider)

    assert result.explanation_source == "fallback"
    assert result.explanation_fallback_used is True
    assert reason_type in result.explanation_fallback_reason
    assert "Manageable with caution" in result.response_text
    assert "Officially approved" not in result.response_text
    assert "guarantees graduation" not in result.response_text
    assert "sensitive detail" not in result.explanation_fallback_reason


@pytest.mark.parametrize(
    "response_code,engine_result,required_text,forbidden_text",
    [
        (
            "SCHEDULE_CONFLICT_FOUND",
            {
                "has_conflict": True,
                "schedule_status": "verified",
                "shared_days": "T R",
                "section_1": {"course": "COP 3530C", "section": "001", "days": "T R", "time": "12:30 PM"},
                "section_2": {"course": "MAC 2312", "section": "006", "days": "T R", "time": "12:00 PM"},
            },
            "Schedule conflict confirmed",
            "No schedule conflict",
        ),
        (
            "NO_SCHEDULE_CONFLICT",
            {
                "has_conflict": False,
                "schedule_status": "verified",
                "section_1": {"course": "COP 3530C", "section": "001", "days": "T R", "time": "12:30 PM"},
                "section_2": {"course": "MAP 3305", "section": "001", "days": "M W", "time": "3:00 PM"},
            },
            "No schedule conflict was found",
            "cannot be determined",
        ),
        (
            "SCHEDULE_UNCERTAIN_TIMING",
            {
                "has_conflict": None,
                "schedule_status": "unknown_timing",
                "reason": "one section has TBA meeting times",
                "section_1": {"course": "CNT 4403", "section": "001", "days": "TBA", "time": "TBA"},
                "section_2": {"course": "COP 3530C", "section": "001", "days": "T R", "time": "12:30 PM"},
            },
            "Cannot verify schedule conflict",
            "No schedule conflict was found",
        ),
    ],
)
def test_schedule_templates_preserve_confirmed_and_unknown_states(
    response_code, engine_result, required_text, forbidden_text
):
    result = render_explanation(
        response_code=response_code,
        target_handler="scheduling_engine",
        current_text="legacy schedule text",
        engine_result=engine_result,
    )

    assert required_text in result.response_text
    assert forbidden_text not in result.response_text
    assert any("Verify meeting details in the official schedule" in item for item in result.limitations)
    if response_code == "SCHEDULE_UNCERTAIN_TIMING":
        assert any("no-conflict conclusion" in item for item in result.limitations)


def test_alternative_template_labels_seats_as_snapshot_and_preserves_limitations():
    result = render_explanation(
        response_code="ALTERNATIVE_SECTIONS_FOUND",
        target_handler="scheduling_engine",
        current_text="legacy. (Note: Requested preference [instructor preference] is not filtered by this prototype.)",
        engine_result={
            "target_section": {"course": "COP 3530C", "section": "001"},
            "count": 1,
            "alternatives": [
                {
                    "course": "COP 3530C",
                    "section": "002",
                    "days": "M W",
                    "time": "2:00 PM",
                    "seats_remaining": 4,
                    "timing_verified": False,
                }
            ],
            "limitations": ["One alternative has unverified or TBA meeting times."],
        },
    )

    assert "candidate alternative section(s)" in result.response_text
    assert "snapshot seats: 4" in result.response_text
    assert "seats open" not in result.response_text
    assert "Limitation:" in result.response_text
    assert "Note: Requested preference" in result.response_text
    assert any("not live registration availability" in item for item in result.limitations)


def test_real_conversation_path_preserves_engine_and_parser_metadata_on_explanation_fallback():
    engine_result = {
        "success": True,
        "student_id": "Z00000001",
        "assessment": "Manageable with caution",
        "proposed_courses": ["COP4331", "MAP3305"],
        "proposed_credits": 6,
        "repeat_course_warning": "Review prior attempts.",
        "recommendations": [],
        "data_warnings": [],
    }
    payload = {
        "message": "Can I take COP 4331 and MAP 3305 together?",
        "student_id": "Z00000001",
        "recent_difficulty": 1,
        "satisfied_with_performance": "yes",
        "work_hours": 5,
    }

    with (
        patch.object(conv_router, "evaluate_compatibility", return_value=engine_result),
        patch.object(conv_router, "_explanation_provider", RaisingProvider()),
    ):
        response = client.post("/conversation", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["response_code"] == "COMPATIBILITY_EVALUATION_COMPLETE"
    assert data["engine_result"] == engine_result
    assert data["parser_source"] == "deterministic"
    assert data["fallback_used"] is False
    assert data["explanation_source"] == "fallback"
    assert data["explanation_fallback_used"] is True
    assert data["explanation_contract_version"] == EXPLANATION_CONTRACT_VERSION
    assert "Manageable with caution" in data["response_text"]


@pytest.mark.parametrize(
    "message,response_code,required_text",
    [
        ("Register me for COP 4331", "ADVISOR_ESCALATION_REQUIRED", "authorized university office"),
        ("What does university policy say about prerequisites?", "FUTURE_RAG_NOT_AVAILABLE", "not enabled"),
    ],
)
def test_real_path_keeps_advisor_and_inactive_rag_boundaries(message, response_code, required_text):
    response = client.post("/conversation", json={"message": message})

    assert response.status_code == 200
    data = response.json()
    assert data["response_code"] == response_code
    assert required_text in data["response_text"]
    assert data["engine_result"] is None
    assert data["explanation_source"] == "deterministic"
