"""Deterministic evidence requirements and local availability assessment.

This module decides whether validated local passages are suitable before any
provider generation. It never performs acquisition or network I/O.
"""
from __future__ import annotations

import re
from collections import defaultdict

from .models import (
    AcquisitionPlan,
    EvidenceAssessment,
    EvidenceChunk,
    EvidenceRequirement,
    EvidenceRequirementPart,
    RetrievedEvidence,
)
from .retriever import Retriever


TOPIC_RE = re.compile(r"\b(topic|topics|cover|covered|content|course description|learn|which course)\b", re.I)
PREREQUISITE_RE = re.compile(r"\b(prerequisite|prerequisites|prereq|required before)\b", re.I)
ASSESSMENT_STEMS = {
    "quiz": re.compile(r"\bquiz(?:zes)?\b", re.I),
    "test": re.compile(r"\btests?\b", re.I),
    "exam": re.compile(r"\bexams?\b", re.I),
    "assignment": re.compile(r"\bassignments?\b", re.I),
    "project": re.compile(r"\bprojects?\b", re.I),
}
ASSESSMENT_CONTEXT_RE = re.compile(
    r"\b(graded|grading|grade|weight|weighted|percent|percentage|points?|policy|late|missed|make[ -]?up|drop|dropped|best|count)\b|%",
    re.I,
)
LATE_RE = re.compile(r"\b(late|missed|make[ -]?up|deadline|after the due date)\b", re.I)
GRADING_RE = re.compile(r"\b(graded|grading|grade|weight|weighted|percent|percentage|points?|drop|dropped|best|count|score)\b|%", re.I)
TOKEN_RE = re.compile(r"[a-z0-9]+")
TOPIC_STOP = {"a", "an", "and", "by", "course", "does", "in", "is", "or", "the", "this"}


def _scope(requirement: EvidenceRequirement) -> dict[str, str | None]:
    return {
        "course_code": requirement.course_code,
        "term_id": requirement.term_id,
        "section": requirement.section,
        "freshness": "unknown",
    }


def classify_evidence_requirement(
    question: str,
    *,
    course_code: str | None,
    term_id: str | None,
    section: str | None,
) -> EvidenceRequirement:
    """Classify only the first bounded informational categories supported by v0."""
    parts: list[EvidenceRequirementPart] = []
    specific_topic: str | None = None
    match = re.search(r"^\s*does\s+[a-z]{3}[\s-]*\d{4}[a-z]?\s+(?:cover|include)\s+(.+?)(?:\?|$)", question, re.I)
    if match:
        specific_topic = match.group(1)
    else:
        match = re.search(r"\bis\s+(.+?)\s+covered\s+(?:in|by)\s+[a-z]{3}[\s-]*\d{4}[a-z]?", question, re.I)
        if match:
            specific_topic = match.group(1)
    if specific_topic:
        terms = [token for token in TOKEN_RE.findall(specific_topic.casefold()) if token not in TOPIC_STOP and len(token) > 1]
        parts.append(EvidenceRequirementPart(
            kind="course_topics",
            source_category="course_description",
            requested_detail="specific_topic",
            subject_terms=list(dict.fromkeys(terms)),
        ))
    elif TOPIC_RE.search(question):
        parts.append(EvidenceRequirementPart(
            kind="course_topics",
            source_category="course_description",
            requested_detail="course_topics",
        ))
    if PREREQUISITE_RE.search(question):
        parts.append(EvidenceRequirementPart(
            kind="published_prerequisites",
            source_category="course_description",
            requested_detail="published_prerequisites",
        ))

    assessment_terms = [name for name, pattern in ASSESSMENT_STEMS.items() if pattern.search(question)]
    if assessment_terms and ASSESSMENT_CONTEXT_RE.search(question):
        detail = "late_policy" if LATE_RE.search(question) else "grading" if GRADING_RE.search(question) else "assessment_policy"
        parts.append(EvidenceRequirementPart(
            kind="section_assessment",
            source_category="syllabus",
            requested_detail=detail,
            subject_terms=assessment_terms,
            requires_term=True,
            requires_section=True,
        ))

    unresolved: list[str] = []
    if parts and not course_code:
        unresolved.append("course_code")
    if any(part.requires_term for part in parts) and not term_id:
        unresolved.append("term_id")
    if any(part.requires_section for part in parts) and not section:
        unresolved.append("section")
    return EvidenceRequirement(
        question=question,
        course_code=course_code,
        term_id=term_id,
        section=section,
        parts=parts,
        unresolved=unresolved,
    )


def _usable(chunk: EvidenceChunk) -> bool:
    return bool(
        chunk.chunk_id.strip()
        and chunk.document_id.strip()
        and chunk.source_version.strip()
        and chunk.locator.strip()
        and chunk.text.strip()
        and chunk.content_sha256.strip()
        and re.match(r"^https?://", chunk.source_url)
    )


def _applies(chunk: EvidenceChunk, requirement: EvidenceRequirement, category: str) -> bool:
    if chunk.course_code != requirement.course_code or chunk.record_category != category or not _usable(chunk):
        return False
    if category == "syllabus":
        return chunk.term_id == requirement.term_id and chunk.section == requirement.section
    return True


def _has_subject(text: str, subject: str) -> bool:
    return bool(ASSESSMENT_STEMS[subject].search(text))


def _supports(part: EvidenceRequirementPart, chunk: EvidenceChunk) -> bool:
    locator = chunk.locator.casefold()
    text = chunk.text
    if part.kind == "course_topics":
        if "course description" not in locator:
            return False
        if part.requested_detail == "specific_topic":
            text_tokens = set(TOKEN_RE.findall(text.casefold()))
            return bool(part.subject_terms) and all(term in text_tokens for term in part.subject_terms)
        return True
    if part.kind == "published_prerequisites":
        return "prerequisite" in locator
    if not all(_has_subject(text, subject) for subject in part.subject_terms):
        return False
    if part.requested_detail == "late_policy":
        return bool(LATE_RE.search(text))
    if part.requested_detail == "grading":
        return bool(GRADING_RE.search(text))
    return True


def _retrieved(chunk: EvidenceChunk, score: float, matched_terms: list[str]) -> RetrievedEvidence:
    return RetrievedEvidence(**chunk.model_dump(), score=score, matched_terms=matched_terms)


def _plan(requirement: EvidenceRequirement, *, categories: list, gap: str, eligible: bool) -> AcquisitionPlan:
    if categories == ["course_description"]:
        capability = "Bounded manual catalog collector: scripts/course_descriptions.py"
    elif categories == ["syllabus"]:
        capability = "Bounded exact-mapping syllabus collector: scripts/syllabus_browser_collect.py; execution remains opt-in."
    elif categories:
        capability = "Use the bounded catalog and/or one-document syllabus collectors for the listed source categories."
    else:
        capability = "No acquisition should run until the evidence gap is resolved."
    return AcquisitionPlan(
        eligible=eligible,
        course_code=requirement.course_code,
        source_categories=categories,
        term_id=requirement.term_id,
        section=requirement.section,
        evidence_gap=gap,
        collector_capability=capability,
        clarification_required=bool(requirement.unresolved),
    )


def assess_evidence(requirement: EvidenceRequirement, retriever: Retriever) -> EvidenceAssessment:
    """Assess source applicability and deterministic passage support separately."""
    categories = list(dict.fromkeys(part.source_category for part in requirement.parts))
    if not requirement.parts:
        return EvidenceAssessment(
            decision="unsupported_information_request",
            reason="The question is outside the bounded evidence categories currently assessed.",
            resolved_scope=_scope(requirement),
            required_source_categories=categories,
            acquisition_plan=_plan(requirement, categories=[], gap="unsupported_information_request", eligible=False),
        )
    if requirement.unresolved:
        return EvidenceAssessment(
            decision="clarification_required",
            reason=f"Required scope is unresolved: {', '.join(requirement.unresolved)}.",
            resolved_scope=_scope(requirement),
            required_source_categories=categories,
            missing_evidence_categories=categories,
            acquisition_plan=_plan(requirement, categories=categories, gap="unresolved_scope", eligible=False),
        )

    chunks = getattr(retriever, "chunks", None)
    if chunks is None:
        return EvidenceAssessment(
            decision="corpus_unavailable",
            reason="The loaded retriever does not expose a validated local evidence inventory.",
            resolved_scope=_scope(requirement),
            required_source_categories=categories,
            missing_evidence_categories=categories,
            acquisition_plan=_plan(requirement, categories=categories, gap="local_corpus_unavailable", eligible=False),
        )

    ranked = retriever.search(
        requirement.question,
        course_codes=[requirement.course_code] if requirement.course_code else None,
        term_id=requirement.term_id,
        section=requirement.section,
        limit=max(4, len(chunks)),
    )
    rank_by_id = {item.chunk_id: item for item in ranked}
    supported_by_part: dict[int, list[EvidenceChunk]] = defaultdict(list)
    absent_categories: list = []
    detail_missing_categories: list = []

    for index, part in enumerate(requirement.parts):
        applicable = [chunk for chunk in chunks if _applies(chunk, requirement, part.source_category)]
        if not applicable:
            absent_categories.append(part.source_category)
            continue
        supporting = [chunk for chunk in applicable if _supports(part, chunk)]
        if not supporting:
            detail_missing_categories.append(part.source_category)
            continue
        supported_by_part[index].extend(supporting)

    supported_parts = len(supported_by_part)
    unique: dict[str, RetrievedEvidence] = {}
    for items in supported_by_part.values():
        for chunk in items:
            ranked_item = rank_by_id.get(chunk.chunk_id)
            unique[chunk.chunk_id] = ranked_item or _retrieved(chunk, 0.0, [])
    evidence = list(unique.values())
    evidence.sort(key=lambda item: (-item.score, item.chunk_id))

    missing = list(dict.fromkeys(absent_categories + detail_missing_categories))
    if supported_parts == len(requirement.parts):
        return EvidenceAssessment(
            decision="ready",
            reason="Applicable validated passages deterministically support every requested information part.",
            resolved_scope=_scope(requirement),
            required_source_categories=categories,
            supporting_evidence=evidence,
        )
    if supported_parts:
        gap = "requested_detail_not_located" if detail_missing_categories else "appropriate_source_absent"
        return EvidenceAssessment(
            decision="partially_supported",
            reason="Only part of the multi-part request has supporting local evidence.",
            resolved_scope=_scope(requirement),
            required_source_categories=categories,
            supporting_evidence=evidence,
            missing_evidence_categories=missing,
            acquisition_plan=_plan(requirement, categories=missing, gap=gap, eligible=bool(absent_categories)),
        )
    if absent_categories:
        return EvidenceAssessment(
            decision="appropriate_source_absent",
            reason="No applicable validated local source exists for the required category and scope.",
            resolved_scope=_scope(requirement),
            required_source_categories=categories,
            missing_evidence_categories=missing,
            acquisition_plan=_plan(requirement, categories=missing, gap="appropriate_source_absent", eligible=True),
        )
    return EvidenceAssessment(
        decision="requested_detail_not_located",
        reason="An applicable source is present, but the requested detail was not found in checked passages.",
        resolved_scope=_scope(requirement),
        required_source_categories=categories,
        missing_evidence_categories=missing,
        acquisition_plan=_plan(requirement, categories=missing, gap="requested_detail_not_located", eligible=False),
    )
