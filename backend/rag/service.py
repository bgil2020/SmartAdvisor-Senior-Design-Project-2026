from __future__ import annotations

import os
import re
from pathlib import Path

from .generation import BaseRAGProvider, provider_from_environment
from .models import RAGResult, RetrievedEvidence
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
    if retriever is None:
        if not path.exists():
            return RAGResult(status="no_relevant_evidence", answer="No validated local RAG corpus is available. Build the corpus before asking informational questions.", generation_source="none", limitations=["No corpus file was loaded."])
        retriever = LexicalRetriever.from_path(path)
    evidence = retriever.search(question, course_codes=course_codes, term_id=term_id, section=section)
    if not evidence:
        scope = ", ".join(course_codes or []) or "the requested scope"
        return RAGResult(status="no_relevant_evidence", answer=f"No relevant validated evidence was found for {scope}. I cannot answer this from the available sources.", generation_source="none", limitations=["Absence from this small corpus does not prove the information is absent from official sources."])
    if not course_codes and len({item.course_code for item in evidence}) > 1:
        return RAGResult(status="clarification", answer="The available evidence applies to multiple courses. Please name the course code you mean.", generation_source="none", sources=[_source(item) for item in evidence], retrieved_evidence=evidence, limitations=["No cross-course claim was generated from ambiguous evidence."])

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
            return RAGResult(status="answered", answer=answer, generation_source="provider", model_id=selected_provider.model_id, sources=[_source(item) for item in used], retrieved_evidence=evidence, limitations=["Citation-ID validation confirms source identity, not the truth of every generated statement."])
        except Exception as exc:
            return RAGResult(status="answered", answer=_fallback(evidence), generation_source="source_excerpt_fallback", generation_fallback_used=True, generation_fallback_reason=f"Provider unavailable or rejected ({type(exc).__name__})", model_id=getattr(selected_provider, "model_id", None), sources=[_source(item) for item in evidence], retrieved_evidence=evidence, limitations=["This is an extractive fallback, not a live LLM-generated answer."])
    return RAGResult(status="answered", answer=_fallback(evidence), generation_source="source_excerpt_fallback", generation_fallback_used=True, generation_fallback_reason="RAG_GENERATION_MODE is not set to gemini", sources=[_source(item) for item in evidence], retrieved_evidence=evidence, limitations=["This is an extractive fallback, not a live LLM-generated answer."])
