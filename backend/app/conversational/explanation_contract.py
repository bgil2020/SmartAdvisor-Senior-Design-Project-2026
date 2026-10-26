"""Versioned, provider-independent explanation guardrails.

The engine result remains authoritative. Optional providers may select only a
backend-owned template and approved evidence references; they cannot provide
free-form prose or new facts. All user-facing wording and limitations are
rendered deterministically by this module.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


EXPLANATION_CONTRACT_VERSION = "1.0"

DEFAULT_EXPLANATION_DISCLAIMER = (
    "Preliminary planning guidance only. SmartAdvisor does not approve overrides, "
    "register students, waive prerequisites, guarantee graduation, or replace "
    "official university policy or advising."
)

PROHIBITED_CLAIMS = (
    "official approval or override granted",
    "registration or enrollment completed",
    "prerequisite waived",
    "graduation guaranteed",
    "unsupported university policy, citation, requirement, or recommendation",
    "catalog-snapshot seats represented as live registration availability",
)

ResultType = Literal[
    "compatibility",
    "schedule_conflict",
    "alternative_sections",
    "clarification",
    "engine_error",
    "advisor_escalation",
    "rag_inactive",
    "unsupported",
]

TemplateId = Literal[
    "compatibility_result",
    "schedule_conflict",
    "schedule_no_conflict",
    "schedule_unknown",
    "alternative_sections",
    "no_alternative_sections",
    "clarification",
    "engine_error",
    "advisor_escalation",
    "rag_inactive",
    "unsupported",
]

LimitationCode = Literal[
    "preliminary_only",
    "official_advising_required",
    "catalog_snapshot",
    "verify_official_schedule",
    "seat_snapshot_not_live",
    "uncertain_timing",
    "authorized_office_required",
    "rag_inactive",
    "engine_unavailable",
]


APPROVED_EVIDENCE_FIELDS: dict[ResultType, frozenset[str]] = {
    "compatibility": frozenset(
        {
            "response.code",
            "engine.assessment",
            "engine.proposed_courses",
            "engine.proposed_credits",
            "engine.repeat_course_warning",
            "engine.recommendations",
            "engine.data_warnings",
        }
    ),
    "schedule_conflict": frozenset(
        {
            "response.code",
            "engine.has_conflict",
            "engine.schedule_status",
            "engine.shared_days",
            "engine.reason",
            "engine.note",
            "engine.section_1",
            "engine.section_2",
        }
    ),
    "alternative_sections": frozenset(
        {
            "response.code",
            "engine.target_section",
            "engine.alternative_count",
            "engine.alternative_candidates",
            "engine.schedule_limitations",
        }
    ),
    "clarification": frozenset(
        {"response.code", "response.missing_context", "response.target_handler"}
    ),
    "engine_error": frozenset({"response.code", "response.target_handler"}),
    "advisor_escalation": frozenset(
        {"response.code", "response.target_handler"}
    ),
    "rag_inactive": frozenset({"response.code", "response.target_handler"}),
    "unsupported": frozenset({"response.code", "response.target_handler"}),
}

LIMITATION_TEXT: dict[LimitationCode, str] = {
    "preliminary_only": "Results are preliminary planning guidance, not an official academic decision.",
    "official_advising_required": "Verify prerequisites, degree requirements, and academic decisions with an authorized advisor.",
    "catalog_snapshot": "Schedule details come from the loaded catalog snapshot and may change.",
    "verify_official_schedule": "Verify meeting details in the official schedule before acting.",
    "seat_snapshot_not_live": "Displayed seat counts are snapshot data, not live registration availability.",
    "uncertain_timing": "Unverified or TBA timing cannot support a no-conflict conclusion.",
    "authorized_office_required": "Only an authorized university office may approve or perform the requested action.",
    "rag_inactive": "Source-grounded policy retrieval is not enabled.",
    "engine_unavailable": "The requested evaluation was not completed; no result should be inferred.",
}


class ApprovedSourceMetadata(BaseModel):
    """Reserved shape for future source-grounded explanations; retrieval is inactive."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    title: str
    publisher: str
    url: str
    accessed_at: str
    content_sha256: str


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_id: str
    value: str | int | float | bool | None | list[str]


class ExplanationProviderPayload(BaseModel):
    """Minimum non-identifying payload allowed across a provider boundary."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["1.0"] = EXPLANATION_CONTRACT_VERSION
    result_type: ResultType
    response_code: str
    expected_template: TemplateId
    evidence: list[EvidenceReference]
    required_evidence_references: list[str]
    required_limitation_codes: list[LimitationCode]
    # Retrieval/RAG stays inactive in this task. The type documents the future
    # metadata boundary while max_length=0 prevents sources from being supplied.
    source_metadata: list[ApprovedSourceMetadata] = Field(default_factory=list, max_length=0)


class ExplanationProposal(BaseModel):
    """Constrained provider proposal: no prose and no provider-authored facts."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["1.0"] = EXPLANATION_CONTRACT_VERSION
    template_id: TemplateId
    evidence_references: list[str]
    limitation_codes: list[LimitationCode]


class ExplanationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response_text: str
    disclaimer: str = DEFAULT_EXPLANATION_DISCLAIMER
    explanation_source: Literal["deterministic", "provider_structured", "fallback"]
    explanation_fallback_used: bool = False
    explanation_fallback_reason: str | None = None
    evidence_references: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    contract_version: Literal["1.0"] = EXPLANATION_CONTRACT_VERSION


class BaseExplanationProvider(ABC):
    """Optional future provider seam. No live implementation is enabled."""

    @abstractmethod
    def propose(self, payload: ExplanationProviderPayload) -> ExplanationProposal | dict[str, Any]:
        raise NotImplementedError


def _section_label(section: Any) -> str | None:
    if not isinstance(section, dict):
        return None
    course = str(section.get("course") or "").strip()
    number = str(section.get("section") or "").strip()
    if not course or not number:
        return None
    days = str(section.get("days") or "").strip()
    meeting_time = str(section.get("time") or "").strip()
    detail = " ".join(value for value in (days, meeting_time) if value)
    return f"{course} section {number}" + (f" ({detail})" if detail else "")


def _result_type(response_code: str, target_handler: str) -> ResultType:
    if response_code == "COMPATIBILITY_EVALUATION_COMPLETE":
        return "compatibility"
    if response_code in {
        "SCHEDULE_CONFLICT_FOUND",
        "NO_SCHEDULE_CONFLICT",
        "SCHEDULE_UNCERTAIN_TIMING",
    }:
        return "schedule_conflict"
    if response_code in {
        "ALTERNATIVE_SECTIONS_FOUND",
        "NO_ALTERNATIVE_SECTIONS_FOUND",
    }:
        return "alternative_sections"
    if response_code == "ADVISOR_ESCALATION_REQUIRED":
        return "advisor_escalation"
    if response_code == "FUTURE_RAG_NOT_AVAILABLE":
        return "rag_inactive"
    if response_code in {
        "ENGINE_EXECUTION_ERROR",
        "ENGINE_EVALUATION_FAILED",
        "SECTION_NOT_FOUND",
    }:
        return "engine_error"
    if response_code in {
        "MISSING_STUDENT_CONTEXT",
        "MISSING_SECTION_DETAILS",
        "MISSING_TARGET_SECTION",
        "MISSING_SCHEDULE_CONTEXT",
        "MISSING_COURSE_CODES",
        "MISSING_SECOND_COURSE",
        "MISSING_SCHEDULE_DETAILS",
        "AMBIGUOUS_REQUEST",
        "AMBIGUOUS_SECTION_MATCH",
        "INVALID_OR_CONFLICTING_DETAILS",
        "CONTRADICTORY_SECTION_DETAILS",
        "EXCESS_SECTIONS_DETECTED",
    }:
        return "clarification"
    if target_handler == "academic_advisor":
        return "advisor_escalation"
    if target_handler == "future_informational_rag":
        return "rag_inactive"
    return "unsupported"


def _template_id(result_type: ResultType, response_code: str) -> TemplateId:
    if result_type == "compatibility":
        return "compatibility_result"
    if result_type == "schedule_conflict":
        if response_code == "SCHEDULE_CONFLICT_FOUND":
            return "schedule_conflict"
        if response_code == "NO_SCHEDULE_CONFLICT":
            return "schedule_no_conflict"
        return "schedule_unknown"
    if result_type == "alternative_sections":
        return (
            "alternative_sections"
            if response_code == "ALTERNATIVE_SECTIONS_FOUND"
            else "no_alternative_sections"
        )
    if result_type == "clarification":
        return "clarification"
    if result_type == "engine_error":
        return "engine_error"
    if result_type == "advisor_escalation":
        return "advisor_escalation"
    if result_type == "rag_inactive":
        return "rag_inactive"
    return "unsupported"


def _required_limitations(result_type: ResultType, response_code: str) -> list[LimitationCode]:
    result: list[LimitationCode] = ["preliminary_only"]
    if result_type == "compatibility":
        result.append("official_advising_required")
    elif result_type == "schedule_conflict":
        result.extend(["catalog_snapshot", "verify_official_schedule"])
        if response_code == "SCHEDULE_UNCERTAIN_TIMING":
            result.append("uncertain_timing")
    elif result_type == "alternative_sections":
        result.extend(
            ["catalog_snapshot", "verify_official_schedule", "seat_snapshot_not_live"]
        )
    elif result_type == "advisor_escalation":
        result.append("authorized_office_required")
    elif result_type == "rag_inactive":
        result.append("rag_inactive")
    elif result_type == "engine_error":
        result.append("engine_unavailable")
    return result


def _build_payload(
    *,
    response_code: str,
    target_handler: str,
    engine_result: dict[str, Any] | None,
    extracted_courses: list[str],
    missing_context: list[str],
) -> ExplanationProviderPayload:
    result_type = _result_type(response_code, target_handler)
    template_id = _template_id(result_type, response_code)
    approved = APPROVED_EVIDENCE_FIELDS[result_type]
    refs: list[EvidenceReference] = []

    def add(reference_id: str, value: Any) -> None:
        if reference_id not in approved or value is None or value == "" or value == []:
            return
        if isinstance(value, tuple):
            value = list(value)
        if isinstance(value, list):
            value = [str(item) for item in value]
        if not isinstance(value, (str, int, float, bool, list)):
            return
        refs.append(EvidenceReference(reference_id=reference_id, value=value))

    engine = engine_result if isinstance(engine_result, dict) else {}
    add("response.code", response_code)

    if result_type == "compatibility":
        add("engine.assessment", engine.get("assessment"))
        add("engine.proposed_courses", engine.get("proposed_courses") or extracted_courses)
        add("engine.proposed_credits", engine.get("proposed_credits"))
        add("engine.repeat_course_warning", engine.get("repeat_course_warning"))
        add("engine.recommendations", engine.get("recommendations"))
        add("engine.data_warnings", engine.get("data_warnings"))
    elif result_type == "schedule_conflict":
        add("engine.has_conflict", engine.get("has_conflict"))
        add("engine.schedule_status", engine.get("schedule_status"))
        add("engine.shared_days", engine.get("shared_days"))
        add("engine.reason", engine.get("reason"))
        add("engine.note", engine.get("note"))
        add("engine.section_1", _section_label(engine.get("section_1")))
        add("engine.section_2", _section_label(engine.get("section_2")))
    elif result_type == "alternative_sections":
        add("engine.target_section", _section_label(engine.get("target_section")))
        add("engine.alternative_count", engine.get("count"))
        candidates = []
        for candidate in engine.get("alternatives", []):
            label = _section_label(candidate)
            if not label:
                continue
            seats = candidate.get("seats_remaining")
            timing = "timing verified" if candidate.get("timing_verified", True) else "timing unverified/TBA"
            seat_text = f", snapshot seats: {seats}" if seats is not None else ""
            candidates.append(f"{label}{seat_text}, {timing}")
        add("engine.alternative_candidates", candidates)
        add("engine.schedule_limitations", engine.get("limitations"))
    else:
        add("response.missing_context", missing_context)
        add("response.target_handler", target_handler)

    # A provider must explicitly acknowledge every approved fact it receives.
    # This prevents it from silently dropping backend warnings or limitations.
    required_refs = [ref.reference_id for ref in refs]

    return ExplanationProviderPayload(
        result_type=result_type,
        response_code=response_code,
        expected_template=template_id,
        evidence=refs,
        required_evidence_references=required_refs,
        required_limitation_codes=_required_limitations(result_type, response_code),
    )


def _render_text(payload: ExplanationProviderPayload, current_text: str) -> str:
    evidence = {item.reference_id: item.value for item in payload.evidence}
    template = payload.expected_template

    def with_preference_note(text: str) -> str:
        marker = "Note: Requested preference"
        if marker not in current_text:
            return text
        return f"{text} ({current_text[current_text.index(marker):]}"

    if template == "compatibility_result":
        courses = ", ".join(evidence.get("engine.proposed_courses", []))
        assessment = evidence.get("engine.assessment", "Assessment unavailable")
        text = f"Workload compatibility evaluation completed for {courses}: {assessment}."
        warning = evidence.get("engine.repeat_course_warning")
        if warning:
            text += f" Backend warning: {warning}"
        data_warnings = evidence.get("engine.data_warnings", [])
        if data_warnings:
            text += f" Data warning: {'; '.join(data_warnings)}"
        recommendations = evidence.get("engine.recommendations", [])
        if recommendations:
            text += f" Backend guidance: {' '.join(recommendations)}"
        return text

    section_1 = evidence.get("engine.section_1", "the first section")
    section_2 = evidence.get("engine.section_2", "the second section")
    if template == "schedule_conflict":
        shared = evidence.get("engine.shared_days")
        shared_text = f" on {shared}" if shared else ""
        return with_preference_note(
            f"Schedule conflict confirmed between {section_1} and {section_2}{shared_text}."
        )
    if template == "schedule_no_conflict":
        note = evidence.get("engine.note")
        note_text = f" Backend note: {note}" if note else ""
        return with_preference_note(
            f"No schedule conflict was found between {section_1} and {section_2}.{note_text}"
        )
    if template == "schedule_unknown":
        reason = evidence.get("engine.reason", "meeting timing is missing or unverified")
        return with_preference_note(
            f"Cannot verify schedule conflict for {section_1} and {section_2}: {reason}. "
            "This is not a no-conflict result."
        )

    if template == "alternative_sections":
        target = evidence.get("engine.target_section", "the target section")
        count = evidence.get("engine.alternative_count", len(evidence.get("engine.alternative_candidates", [])))
        candidates = evidence.get("engine.alternative_candidates", [])
        text = (
            f"Found {count} candidate alternative section(s) for {target} in the loaded "
            f"catalog snapshot: {'; '.join(candidates)}."
        )
        limits = evidence.get("engine.schedule_limitations", [])
        if limits:
            text += f" Limitation: {'; '.join(limits)}"
        return with_preference_note(text)
    if template == "no_alternative_sections":
        target = evidence.get("engine.target_section", "the target section")
        return (
            f"No candidate alternatives were found for {target} in the loaded catalog snapshot. "
            "This does not establish current registration availability."
        )

    if template == "engine_error":
        if payload.response_code == "SECTION_NOT_FOUND":
            return current_text
        return "The requested evaluation could not be completed. No academic or scheduling result should be inferred."
    if template == "advisor_escalation":
        return "An academic advisor or authorized university office must make the official decision or perform the requested action."
    if template == "rag_inactive":
        return "Source-grounded policy or catalog explanation is not enabled. Consult the official source or an authorized advisor."

    # Existing clarification/unsupported messages are already deterministic,
    # response-code-specific templates owned by the application.
    return current_text or "The request could not be completed with the available information."


def _validate_proposal(
    proposal: ExplanationProposal,
    payload: ExplanationProviderPayload,
) -> None:
    if proposal.template_id != payload.expected_template:
        raise ValueError("Proposal selected a template inconsistent with the backend result.")

    known_refs = {ref.reference_id for ref in payload.evidence}
    proposed_refs = set(proposal.evidence_references)
    if not proposed_refs.issubset(known_refs):
        raise ValueError("Proposal referenced unsupported or invented evidence.")
    if not set(payload.required_evidence_references).issubset(proposed_refs):
        raise ValueError("Proposal omitted required authoritative evidence.")

    if not set(payload.required_limitation_codes).issubset(set(proposal.limitation_codes)):
        raise ValueError("Proposal omitted required limitations.")


def render_explanation(
    *,
    response_code: str,
    target_handler: str,
    current_text: str,
    engine_result: dict[str, Any] | None = None,
    extracted_courses: list[str] | None = None,
    missing_context: list[str] | None = None,
    provider: BaseExplanationProvider | None = None,
) -> ExplanationResult:
    """Render a guarded explanation without changing engine facts or status."""

    payload = _build_payload(
        response_code=response_code,
        target_handler=target_handler,
        engine_result=engine_result,
        extracted_courses=extracted_courses or [],
        missing_context=missing_context or [],
    )
    text = _render_text(payload, current_text)
    all_refs = [item.reference_id for item in payload.evidence]
    limitations = [LIMITATION_TEXT[code] for code in payload.required_limitation_codes]

    if provider is None:
        return ExplanationResult(
            response_text=text,
            explanation_source="deterministic",
            evidence_references=all_refs,
            limitations=limitations,
        )

    try:
        raw_proposal = provider.propose(payload)
        proposal = (
            raw_proposal
            if isinstance(raw_proposal, ExplanationProposal)
            else ExplanationProposal.model_validate(raw_proposal)
        )
        _validate_proposal(proposal, payload)
        return ExplanationResult(
            response_text=text,
            explanation_source="provider_structured",
            evidence_references=proposal.evidence_references,
            limitations=limitations,
        )
    except Exception as exc:
        # Do not expose provider text, payloads, or exceptions. The class name is
        # sufficient observability and cannot alter authoritative response data.
        return ExplanationResult(
            response_text=text,
            explanation_source="fallback",
            explanation_fallback_used=True,
            explanation_fallback_reason=f"Explanation provider rejected ({type(exc).__name__})",
            evidence_references=all_refs,
            limitations=limitations,
        )
