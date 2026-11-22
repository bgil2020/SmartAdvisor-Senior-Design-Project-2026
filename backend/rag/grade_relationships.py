"""Narrow validation for explicit grade/range relationships.

This module does not provide universal semantic verification. It only compares
grade labels with parseable ranges, intervals, or thresholds in cited text.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

NUMBER_TOKEN = r"\d+(?:\.\d+)?%?"
GRADE_LABEL = r"[ABCDF][+-]?"
RANGE_SEPARATOR = r"(?:-|–|—|to|through)"


def normalize_number(value: str) -> str:
    try:
        normalized = Decimal(value.rstrip("%")).normalize()
    except InvalidOperation:
        return value
    rendered = format(normalized, "f")
    return "0" if rendered in {"-0", ""} else rendered


def _relation_sort_key(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(item.get("grade", "")), str(item.get("kind", "")),
        str(item.get("low", item.get("value", ""))), str(item.get("high", item.get("operator", ""))),
    )


def extract_grade_relationships(text: str) -> list[dict[str, Any]]:
    """Extract bounded grade relationships while retaining operator semantics."""
    label_first = re.compile(
        rf"(?<![A-Za-z0-9])(?P<label>{GRADE_LABEL})(?![A-Za-z0-9+-])"
        rf"[ \t]*(?:is|:|=|\()?[ \t]*(?P<low>{NUMBER_TOKEN})[ \t]*(?P<separator>{RANGE_SEPARATOR})[ \t]*(?P<high>{NUMBER_TOKEN})",
        re.IGNORECASE,
    )
    range_first = re.compile(
        rf"(?P<low>{NUMBER_TOKEN})[ \t]*(?P<separator>{RANGE_SEPARATOR})[ \t]*(?P<high>{NUMBER_TOKEN})[ \t]*"
        rf"(?P<label>{GRADE_LABEL})(?![A-Za-z0-9+-])",
        re.IGNORECASE,
    )
    interval = re.compile(
        rf"(?<![A-Za-z0-9])(?P<label>{GRADE_LABEL})(?![A-Za-z0-9+-])\s*(?:is|:|=)?\s*"
        rf"(?P<left>[\[(])\s*(?P<low>{NUMBER_TOKEN})\s*,\s*(?P<high>{NUMBER_TOKEN})\s*(?P<right>[\])])",
        re.IGNORECASE,
    )
    threshold = re.compile(
        rf"(?<![A-Za-z0-9])(?P<label>{GRADE_LABEL})(?![A-Za-z0-9+-])\s*(?:is|:|=)?\s*"
        rf"(?P<operator>>=|<=|>|<|at\s+least|at\s+most|more\s+than|less\s+than)\s*(?P<value>{NUMBER_TOKEN})",
        re.IGNORECASE,
    )
    relationships: dict[tuple[Any, ...], dict[str, Any]] = {}
    for pattern in (label_first, range_first):
        for match in pattern.finditer(text):
            item = {
                "grade": match.group("label").upper(),
                "kind": "range",
                "low": normalize_number(match.group("low")),
                "high": normalize_number(match.group("high")),
                "low_inclusive": "unspecified",
                "high_inclusive": "unspecified",
                "notation": match.group("separator").casefold(),
            }
            relationships[(item["grade"], "range", item["low"], item["high"], "unspecified", "unspecified")] = item
    for match in interval.finditer(text):
        item = {
            "grade": match.group("label").upper(),
            "kind": "range",
            "low": normalize_number(match.group("low")),
            "high": normalize_number(match.group("high")),
            "low_inclusive": match.group("left") == "[",
            "high_inclusive": match.group("right") == "]",
            "notation": "interval",
        }
        relationships[(item["grade"], "range", item["low"], item["high"], item["low_inclusive"], item["high_inclusive"])] = item
    operator_map = {
        "at least": ">=", "at most": "<=", "more than": ">", "less than": "<",
    }
    for match in threshold.finditer(text):
        raw_operator = re.sub(r"\s+", " ", match.group("operator").casefold())
        item = {
            "grade": match.group("label").upper(),
            "kind": "threshold",
            "operator": operator_map.get(raw_operator, raw_operator),
            "value": normalize_number(match.group("value")),
            "notation": raw_operator,
        }
        relationships[(item["grade"], "threshold", item["operator"], item["value"])] = item
    return sorted(relationships.values(), key=_relation_sort_key)


def _grade_label_candidates(text: str) -> set[str]:
    near_number = re.compile(
        rf"(?<![A-Za-z0-9])(?P<label>{GRADE_LABEL})(?=(?:\s|:|=|\(|\[)*{NUMBER_TOKEN})",
        re.IGNORECASE,
    )
    return {match.group("label").upper() for match in near_number.finditer(text)}


def _compatible(answer: dict[str, Any], source: dict[str, Any]) -> bool:
    if answer.get("grade") != source.get("grade") or answer.get("kind") != source.get("kind"):
        return False
    if answer.get("kind") == "threshold":
        return answer.get("operator") == source.get("operator") and answer.get("value") == source.get("value")
    if answer.get("low") != source.get("low") or answer.get("high") != source.get("high"):
        return False
    for field in ("low_inclusive", "high_inclusive"):
        left, right = answer.get(field), source.get(field)
        if left != "unspecified" and right != "unspecified" and left != right:
            return False
    return True


def validate_grade_relationships(answer_text: str, source_texts: Iterable[str]) -> dict[str, Any]:
    """Return a bounded relationship verdict suitable for enforcement or evidence."""
    source_text = "\n".join(source_texts)
    answer = extract_grade_relationships(answer_text)
    source = extract_grade_relationships(source_text)
    source_candidates = _grade_label_candidates(source_text)
    extracted_source_grades = {item["grade"] for item in source}
    if not answer:
        extraction = "not_applicable"
    elif not source:
        extraction = "indeterminate"
    elif source_candidates - extracted_source_grades:
        extraction = "partial"
    else:
        extraction = "succeeded"

    comparison = []
    for claim in answer[:16]:
        source_for_grade = [item for item in source if item.get("grade") == claim.get("grade")]
        if any(_compatible(claim, item) for item in source_for_grade):
            status = "match"
        elif extraction == "succeeded":
            status = "mismatch"
        else:
            status = "unknown"
        comparison.append({
            "grade": claim.get("grade"),
            "source_relationships": source_for_grade[:4],
            "answer_relationship": claim,
            "status": status,
        })

    if extraction == "not_applicable":
        verdict = "not_applicable"
    elif extraction != "succeeded" or any(item["status"] == "unknown" for item in comparison):
        verdict = "inconclusive"
    elif any(item["status"] == "mismatch" for item in comparison):
        verdict = "incorrect"
    else:
        verdict = "verified"
    return {
        "verdict": verdict,
        "answer_relationship_count": len(answer),
        "source_relationship_count": len(source),
        "source_extraction": extraction,
        "comparison": comparison,
    }


class GradeRelationshipIncorrect(ValueError):
    """A generated explicit grade relationship contradicts cited evidence."""


class GradeRelationshipInconclusive(ValueError):
    """The cited evidence could not be parsed well enough to verify the claim."""
