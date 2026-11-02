"""Dependency-free lexical retriever with strict applicability filters."""
from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Protocol

from .corpus import load_corpus
from .models import EvidenceChunk, RetrievedEvidence

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP = {"a", "an", "and", "are", "does", "for", "in", "is", "it", "of", "on", "the", "to", "what", "which", "with"}


def tokens(text: str) -> list[str]:
    return [token for token in TOKEN_RE.findall(text.casefold()) if token not in STOP and len(token) > 1]


class Retriever(Protocol):
    def search(self, query: str, *, course_codes: list[str] | None = None, term_id: str | None = None, section: str | None = None, limit: int = 4) -> list[RetrievedEvidence]: ...


class LexicalRetriever:
    def __init__(self, chunks: list[EvidenceChunk]):
        self.chunks = chunks
        self._terms = [Counter(tokens(f"{c.course_code} {c.title} {c.locator} {c.text}")) for c in chunks]
        document_frequency = Counter(term for counts in self._terms for term in counts)
        self._idf = {term: math.log((1 + len(chunks)) / (1 + count)) + 1 for term, count in document_frequency.items()}

    @classmethod
    def from_path(cls, path: Path) -> "LexicalRetriever":
        corpus = load_corpus(path)
        return cls([EvidenceChunk.model_validate(item) for item in corpus["chunks"]])

    def search(self, query: str, *, course_codes: list[str] | None = None, term_id: str | None = None, section: str | None = None, limit: int = 4) -> list[RetrievedEvidence]:
        query_terms = Counter(tokens(query))
        requested = {re.sub(r"[^A-Z0-9]", "", code.upper()) for code in course_codes or []}
        # Course identity is an applicability filter, not evidence that an
        # unrelated fact is present in the course source.
        for code in requested:
            query_terms.pop(code.casefold(), None)
        ranked: list[RetrievedEvidence] = []
        for chunk, counts in zip(self.chunks, self._terms):
            if requested and chunk.course_code not in requested:
                continue
            if term_id and chunk.record_category == "syllabus" and chunk.term_id != str(term_id):
                continue
            if section and chunk.record_category == "syllabus" and chunk.section != str(section):
                continue
            matched = sorted(set(query_terms) & set(counts))
            score = sum(self._idf.get(term, 0) * min(query_terms[term], counts[term]) for term in matched)
            if not matched:
                continue
            if score > 0:
                ranked.append(RetrievedEvidence(**chunk.model_dump(), score=round(score, 6), matched_terms=matched))
        ranked.sort(key=lambda item: (-item.score, item.chunk_id))
        return ranked[:limit]
