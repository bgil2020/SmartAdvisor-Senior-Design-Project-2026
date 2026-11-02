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
