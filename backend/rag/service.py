from __future__ import annotations

import os
import re
from pathlib import Path

from .generation import BaseRAGProvider, provider_from_environment
from .models import AcquisitionPlan, EvidenceAssessment, RAGResult, RetrievedEvidence
from .readiness import assess_evidence, classify_evidence_requirement
from .retriever import LexicalRetriever, Retriever

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = ROOT / "data" / "rag" / "local-corpus.json"


def _source(item: RetrievedEvidence) -> dict:
    return {
        "source_id": item.chunk_id,
        "document_id": item.document_id,
        "course_code": item.course_code,
        "record_category": item.record_category,
        "term_id": item.term_id,
        "term_name": item.term_name,
        "section": item.section,
        "title": item.title,
        "locator": item.locator,
        "url": item.source_url,
        "source_version": item.source_version,
        "content_sha256": item.content_sha256,
        "freshness": "unknown",
    }


def _fallback(evidence: list[RetrievedEvidence]) -> str:
    excerpts = []
    for item in evidence[:3]:
        clean = re.sub(r"\s+", " ", item.text).strip()
        excerpts.append(f"{item.course_code} — {item.locator}: {clean} [{item.chunk_id}]")
    return "Source-excerpt fallback (no live model answer): " + " ".join(excerpts)


def answer_information_question(
    question: str,
    *,
    course_codes: list[str] | None = None,
    term_id: str | None = None,
    section: str | None = None,
    retriever: Retriever | None = None,
    provider: BaseRAGProvider | None = None,
    corpus_path: Path | None = None,
) -> RAGResult:
    path = corpus_path or Path(os.getenv("RAG_CORPUS_PATH", str(DEFAULT_CORPUS)))
    if not path.is_absolute():
        path = ROOT / path
    normalized_courses = list(dict.fromkeys(course_codes or []))
    requirement = classify_evidence_requirement(
        question,
        course_code=normalized_courses[0] if len(normalized_courses) == 1 else None,
        term_id=str(term_id) if term_id is not None else None,
        section=str(section) if section is not None else None,
    )
    categories = list(dict.fromkeys(part.source_category for part in requirement.parts))
    scope = {
        "course_code": requirement.course_code,
        "term_id": requirement.term_id,
        "section": requirement.section,
        "freshness": "unknown",
    }

    if len(normalized_courses) > 1:
        return RAGResult(
            status="clarification",
            answer="Please name one course for this informational request.",
            generation_source="none",
            limitations=["No cross-course claim was generated from ambiguous scope."],
            evidence_decision="clarification_required",
            evidence_reason="Multiple course identities were supplied.",
            resolved_scope=scope,
            required_source_categories=categories,
            missing_evidence_categories=categories,
            acquisition_plan=AcquisitionPlan(
                eligible=False,
                source_categories=categories,
                evidence_gap="ambiguous_course_scope",
                collector_capability="No acquisition should run until one course is identified.",
                clarification_required=True,
            ),
        )
    if not requirement.parts:
        return RAGResult(
            status="no_relevant_evidence",
            answer="This informational request is outside the bounded evidence checks currently supported, so I cannot answer it from the available sources.",
            generation_source="none",
            limitations=["Supported checks currently cover course topics, published prerequisites, and section assessment rules."],
            evidence_decision="unsupported_information_request",
            evidence_reason="No supported evidence requirement was identified.",
            resolved_scope=scope,
            acquisition_plan=AcquisitionPlan(
                eligible=False,
                course_code=requirement.course_code,
                evidence_gap="unsupported_information_request",
                collector_capability="No acquisition should run for an unsupported information category.",
            ),
        )
    if requirement.unresolved:
        needed = ", ".join(requirement.unresolved)
        return RAGResult(
            status="clarification",
            answer=f"Please provide the missing informational scope: {needed}.",
            generation_source="none",
            limitations=["The system does not infer term or section from the only cached syllabus."],
            evidence_decision="clarification_required",
            evidence_reason=f"Required scope is unresolved: {needed}.",
            resolved_scope=scope,
            required_source_categories=categories,
            missing_evidence_categories=categories,
            acquisition_plan=AcquisitionPlan(
                eligible=False,
                course_code=requirement.course_code,
                source_categories=categories,
                term_id=requirement.term_id,
                section=requirement.section,
                evidence_gap="unresolved_scope",
                collector_capability="No acquisition should run until course, term, and section requirements are resolved.",
                clarification_required=True,
            ),
        )
    if retriever is None:
        if not path.exists():
            return RAGResult(
                status="no_relevant_evidence",
                answer="No validated local RAG corpus is available. Restore or build the corpus before assessing this question.",
                generation_source="none",
                limitations=["A missing corpus does not prove that the course or source does not exist."],
                evidence_decision="corpus_unavailable",
                evidence_reason="The configured corpus file does not exist.",
                resolved_scope=scope,
                required_source_categories=categories,
                missing_evidence_categories=categories,
                acquisition_plan=AcquisitionPlan(
                    eligible=False,
                    course_code=requirement.course_code,
                    source_categories=categories,
                    term_id=requirement.term_id,
                    section=requirement.section,
                    evidence_gap="local_corpus_unavailable",
                    collector_capability="Restore or explicitly rebuild the validated local corpus before considering acquisition.",
                ),
            )
        try:
            retriever = LexicalRetriever.from_path(path)
        except (OSError, ValueError, TypeError) as exc:
            return RAGResult(
                status="no_relevant_evidence",
                answer="The configured local RAG corpus could not be read safely. Repair or rebuild it before assessing this question.",
                generation_source="none",
                limitations=["An unreadable corpus does not prove that requested evidence is absent."],
                evidence_decision="corpus_unavailable",
                evidence_reason=f"Corpus load failed ({type(exc).__name__}).",
                resolved_scope=scope,
                required_source_categories=categories,
                missing_evidence_categories=categories,
                acquisition_plan=AcquisitionPlan(
                    eligible=False,
                    course_code=requirement.course_code,
                    source_categories=categories,
                    term_id=requirement.term_id,
                    section=requirement.section,
                    evidence_gap="local_corpus_unreadable",
                    collector_capability="Repair or explicitly rebuild the validated local corpus before considering acquisition.",
                ),
            )

    assessment = assess_evidence(requirement, retriever)
    evidence = assessment.supporting_evidence
    plan = assessment.acquisition_plan
    common = {
        "evidence_decision": assessment.decision,
        "evidence_reason": assessment.reason,
        "resolved_scope": assessment.resolved_scope,
        "required_source_categories": assessment.required_source_categories,
        "supporting_source_ids": [item.chunk_id for item in evidence],
        "missing_evidence_categories": assessment.missing_evidence_categories,
        "acquisition_eligible": bool(plan and plan.eligible),
        "acquisition_plan": plan,
    }
    if assessment.decision != "ready":
        if assessment.decision == "appropriate_source_absent":
            answer = "No applicable validated local source is available for the requested scope. This is an evidence gap, not proof that the source does not exist."
        elif assessment.decision == "requested_detail_not_located":
            answer = "The appropriate source is present, but the requested detail was not found in the checked evidence. I cannot answer it or infer a policy from a document's existence."
        elif assessment.decision == "partially_supported":
            answer = "Only part of this request is supported by the checked evidence, so no combined answer was generated."
        elif assessment.decision == "clarification_required":
            answer = "Please clarify the missing course, term, or section before evidence can be assessed."
        else:
            answer = "The local evidence could not be assessed safely, so no answer was generated."
        return RAGResult(
            status="clarification" if assessment.decision == "clarification_required" else "no_relevant_evidence",
            answer=answer,
            generation_source="none",
            sources=[_source(item) for item in evidence],
            retrieved_evidence=evidence,
            limitations=[
                "Not found in the checked evidence is not proof of absence from university sources.",
                "Source freshness is unknown in the current chunk contract.",
            ],
            **common,
        )

    selected_provider = provider if provider is not None else provider_from_environment()
    if selected_provider is not None:
        try:
            proposal = selected_provider.generate(question, evidence)
            known = {item.chunk_id for item in evidence}
            cited = set(proposal.cited_source_ids)
            if not cited or not cited.issubset(known):
                raise ValueError("Provider cited an unknown or missing source ID")
            used = [item for item in evidence if item.chunk_id in cited]
            inline_citations = " ".join(f"[{source_id}]" for source_id in proposal.cited_source_ids)
            answer = proposal.answer if all(f"[{source_id}]" in proposal.answer for source_id in proposal.cited_source_ids) else f"{proposal.answer} {inline_citations}"
            return RAGResult(status="answered", answer=answer, generation_source="provider", model_id=selected_provider.model_id, sources=[_source(item) for item in used], retrieved_evidence=evidence, limitations=["Citation-ID validation confirms source identity, not the truth of every generated statement.", "Source freshness is unknown in the current chunk contract."], **common)
        except Exception as exc:
            return RAGResult(status="answered", answer=_fallback(evidence), generation_source="source_excerpt_fallback", generation_fallback_used=True, generation_fallback_reason=f"Provider unavailable or rejected ({type(exc).__name__})", model_id=getattr(selected_provider, "model_id", None), sources=[_source(item) for item in evidence], retrieved_evidence=evidence, limitations=["This is an extractive fallback, not a live LLM-generated answer.", "Source freshness is unknown in the current chunk contract."], **common)
    return RAGResult(status="answered", answer=_fallback(evidence), generation_source="source_excerpt_fallback", generation_fallback_used=True, generation_fallback_reason="RAG_GENERATION_MODE is not set to gemini", sources=[_source(item) for item in evidence], retrieved_evidence=evidence, limitations=["This is an extractive fallback, not a live LLM-generated answer.", "Source freshness is unknown in the current chunk contract."], **common)
