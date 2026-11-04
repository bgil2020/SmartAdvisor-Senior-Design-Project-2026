from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class EvidenceChunk(BaseModel):
    chunk_id: str
    document_id: str
    source_version: str
    record_category: Literal["course_description", "syllabus"]
    course_code: str
    term_id: str | None = None
    term_name: str | None = None
    section: str | None = None
    title: str
    locator: str
    source_url: str
    text: str
    content_sha256: str
    limitations: list[str] = Field(default_factory=list)


class RetrievedEvidence(EvidenceChunk):
    score: float
    matched_terms: list[str] = Field(default_factory=list)


SourceCategory = Literal["course_description", "syllabus"]


class EvidenceRequirementPart(BaseModel):
    kind: Literal["course_topics", "published_prerequisites", "section_assessment"]
    source_category: SourceCategory
    requested_detail: str
    subject_terms: list[str] = Field(default_factory=list)
    requires_term: bool = False
    requires_section: bool = False


class EvidenceRequirement(BaseModel):
    question: str
    course_code: str | None = None
    term_id: str | None = None
    section: str | None = None
    parts: list[EvidenceRequirementPart] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)


class AcquisitionPlan(BaseModel):
    execute: Literal[False] = False
    eligible: bool
    course_code: str | None = None
    source_categories: list[SourceCategory] = Field(default_factory=list)
    term_id: str | None = None
    section: str | None = None
    evidence_gap: str
    collector_capability: str
    clarification_required: bool = False
    manual_action_required: bool = True


EvidenceDecision = Literal[
    "ready",
    "clarification_required",
    "corpus_unavailable",
    "appropriate_source_absent",
    "requested_detail_not_located",
    "partially_supported",
    "unsupported_information_request",
    "conflicting_scope",
]


class EvidenceAssessment(BaseModel):
    decision: EvidenceDecision
    reason: str
    resolved_scope: dict[str, str | None] = Field(default_factory=dict)
    required_source_categories: list[SourceCategory] = Field(default_factory=list)
    supporting_evidence: list[RetrievedEvidence] = Field(default_factory=list)
    missing_evidence_categories: list[SourceCategory] = Field(default_factory=list)
    acquisition_plan: AcquisitionPlan | None = None


class RAGResult(BaseModel):
    status: Literal["answered", "clarification", "no_relevant_evidence"]
    answer: str
    generation_source: Literal["provider", "source_excerpt_fallback", "none"]
    generation_fallback_used: bool = False
    generation_fallback_reason: str | None = None
    model_id: str | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_evidence: list[RetrievedEvidence] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence_decision: EvidenceDecision = "unsupported_information_request"
    evidence_reason: str | None = None
    resolved_scope: dict[str, str | None] = Field(default_factory=dict)
    required_source_categories: list[SourceCategory] = Field(default_factory=list)
    supporting_source_ids: list[str] = Field(default_factory=list)
    missing_evidence_categories: list[SourceCategory] = Field(default_factory=list)
    acquisition_eligible: bool = False
    acquisition_plan: AcquisitionPlan | None = None
