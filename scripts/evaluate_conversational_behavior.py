"""Reproducible offline/live conversational evaluation harness.

Live requests are strictly opt-in via ``--live``. The default run is offline,
uses deterministic parsing, and never requires a provider key.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.api import app
import backend.conversational_router as conversation_router
from backend.app.conversational.hybrid_parser import (
    HybridConversationalParser,
    parse_deterministic,
)
from backend.app.conversational.explanation_contract import BaseExplanationProvider


DATASET_PATH = ROOT / "backend/tests/fixtures/conversational_prompt_dataset.json"
CASES_PATH = ROOT / "docs/evaluation/matched_cases.json"
RESULTS_PATH = ROOT / "docs/evaluation/conversational_evaluation_results.json"
CSV_PATH = ROOT / "docs/evaluation/conversational_comparison.csv"
OFFLINE_RESULTS_PATH = ROOT / ".local-report/task-3-offline-results.json"
OFFLINE_CSV_PATH = ROOT / ".local-report/task-3-offline-comparison.csv"
APPROVED_LIVE_MODEL = "gemini-3.5-flash-lite"
MAX_LIVE_ATTEMPTS = 12
PRIVATE_ENGINE_RESULT_FIELDS = {
    "student_id",
    "student_name",
    "major",
    "recent_credits",
    "academic_history",
    "completed_courses",
    "previously_completed_courses",
    "recent_courses",
}


@contextmanager
def process_environment(**updates: str | None):
    original = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalized_pairs(parsed: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"course": item["course"], "section": item["section"]}
        for item in parsed.get("course_section_pairs", [])
    ]


def expected_value_matches(actual: Any, expected: Any) -> bool:
    return actual in expected if isinstance(expected, list) else actual == expected


def sanitize_engine_result(value: Any) -> Any:
    """Remove profile/history fields while retaining evaluation-relevant facts."""
    if isinstance(value, dict):
        return {
            key: sanitize_engine_result(item)
            for key, item in value.items()
            if key not in PRIVATE_ENGINE_RESULT_FIELDS
        }
    if isinstance(value, list):
        return [sanitize_engine_result(item) for item in value]
    return value


def score_case(case: dict[str, Any], parsed: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    expected_entities = case["expected_entities"]
    expected_endpoint = case["expected_endpoint"]
    actual_pairs = normalized_pairs(parsed)
    expected_pairs = expected_entities["course_section_pairs"]

    def unordered_strings(values: list[Any]) -> list[str]:
        return sorted(str(value) for value in values)

    def unordered_pairs(values: list[dict[str, str]]) -> list[tuple[str, str]]:
        return sorted((value["course"], value["section"]) for value in values)

    entity_checks = {
        "course_codes": unordered_strings(parsed.get("course_codes", []))
        == unordered_strings(expected_entities["course_codes"]),
        "crns": unordered_strings(parsed.get("crns", []))
        == unordered_strings(expected_entities["crns"]),
        "course_section_pairs": unordered_pairs(actual_pairs) == unordered_pairs(expected_pairs),
    }
    combined_text = " ".join(
        [
            str(response.get("response_text", "")),
            str(response.get("disclaimer", "")),
            " ".join(response.get("explanation_limitations", [])),
        ]
    ).lower()
    required_checks = {
        text: text.lower() in combined_text for text in expected_endpoint.get("required_text", [])
    }
    required_any_checks = {
        " | ".join(group): any(option.lower() in combined_text for option in group)
        for group in expected_endpoint.get("required_any_text_groups", [])
    }
    forbidden_checks = {
        text: text.lower() not in combined_text for text in expected_endpoint.get("forbidden_text", [])
    }
    return {
        "intent_correct": parsed.get("intent") in case["expected_intents"],
        "entity_fields": entity_checks,
        "entity_exact": all(entity_checks.values()),
        "association_applicable": bool(expected_pairs),
        "association_exact": unordered_pairs(actual_pairs) == unordered_pairs(expected_pairs),
        "handler_correct": expected_value_matches(
            response.get("target_handler"), expected_endpoint["target_handler"]
        ),
        "disposition_correct": expected_value_matches(
            response.get("disposition"), expected_endpoint["disposition"]
        ),
        "engine_behavior_correct": response.get("engine_executed")
        is expected_endpoint["engine_executed"],
        "response_code_correct": response.get("response_code") in expected_endpoint["response_codes"],
        "required_text": required_checks,
        "required_any_text": required_any_checks,
        "required_limitations_correct": all(required_checks.values())
        and all(required_any_checks.values()),
        "forbidden_text": forbidden_checks,
        "unsafe_outcome": not all(forbidden_checks.values()),
    }


def execute_case(case: dict[str, Any], mode: str) -> dict[str, Any]:
    request_json = {"message": case["prompt"], **case["application_context"]}
    captured: dict[str, Any] = {}
    real_parse_query = conversation_router.parse_query

    def capture_parse(message: str, context: dict[str, Any] | None = None):
        result = real_parse_query(message, context=context)
        captured["parsed"] = result.model_dump()
        return result

    started = time.perf_counter()
    with patch.object(conversation_router, "parse_query", side_effect=capture_parse):
        response = TestClient(app).post("/conversation", json=request_json)
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    body = response.json()
    parsed = captured.get("parsed", {})
    endpoint = {
        key: body.get(key)
        for key in (
            "disposition",
            "target_handler",
            "response_code",
            "response_text",
            "engine_executed",
            "engine_result",
            "parser_source",
            "fallback_used",
            "fallback_reason",
            "model_id",
            "explanation_source",
            "explanation_fallback_used",
            "explanation_fallback_reason",
            "explanation_contract_version",
            "evidence_references",
            "explanation_limitations",
            "disclaimer",
        )
    }
    endpoint["engine_result"] = sanitize_engine_result(endpoint["engine_result"])
    return {
        "case_id": case["case_id"],
        "mode": mode,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model_id": parsed.get("model_id"),
        "application_input": request_json,
        "validated_parse": {
            key: parsed.get(key)
            for key in (
                "intent",
                "course_codes",
                "section_identifiers",
                "course_section_pairs",
                "crns",
                "schedule_constraints",
                "modality_preference",
                "is_uncertain",
                "uncertainty_reason",
                "needs_clarification",
                "missing_fields",
                "validation_errors",
                "parser_source",
                "fallback_used",
                "fallback_reason",
                "model_id",
            )
        },
        "http_status": response.status_code,
        "application_status": body.get("status"),
        "latency_ms": latency_ms,
        "endpoint": endpoint,
        "scores": score_case(case, parsed, body),
    }


def deterministic_dataset_evaluation() -> dict[str, Any]:
    rows = []
    for item in load_json(DATASET_PATH):
        parsed = parse_deterministic(item["prompt"])
        rows.append(
            {
                "case_id": item["id"],
                "source_label": item["source_label"],
                "expected_intent": item["expected_classifier_intent"],
                "actual_intent": parsed.intent,
                "correct": parsed.intent == item["expected_classifier_intent"],
            }
        )
    return {
        "total": len(rows),
        "correct": sum(row["correct"] for row in rows),
        "rows": rows,
    }


class RaisingParser:
    def __init__(self, exc: Exception):
        self.exc = exc
        self._client = object()

    def parse(self, message: str, context: dict[str, Any] | None = None):
        raise self.exc


class UnsafeExplanationProvider(BaseExplanationProvider):
    def propose(self, payload):
        return {
            "contract_version": "1.0",
            "template_id": payload.expected_template,
            "evidence_references": payload.required_evidence_references,
            "limitation_codes": payload.required_limitation_codes,
            "official_claim": "Registration completed and graduation guaranteed.",
        }


class FailingExplanationProvider(BaseExplanationProvider):
    def propose(self, payload):
        raise TimeoutError("synthetic explanation timeout with private detail")


def offline_safety_evaluation() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    for check_id, exc, expected_reason in (
        ("SF-001", TimeoutError("synthetic provider timeout"), "Provider request timed out"),
        ("SF-002", ValueError("schema validation failed"), "Model output failed schema validation"),
        ("SF-003", ValueError("invented course COT9999"), "Model output contained ungrounded or invented entities"),
    ):
        dispatcher = HybridConversationalParser(gemini_parser=RaisingParser(exc), force_mode="hybrid")
        with patch.object(conversation_router, "parse_query", side_effect=dispatcher.parse):
            body = TestClient(app).post(
                "/conversation", json={"message": "Can I take COP 3330 and CEN 4010 together?"}
            ).json()
        passed = (
            body["parser_source"] == "fallback"
            and body["fallback_used"] is True
            and body["fallback_reason"] == expected_reason
            and body["engine_executed"] is False
            and body["explanation_source"] == "deterministic"
        )
        checks.append(
            {
                "check_id": check_id,
                "simulation": type(exc).__name__,
                "passed": passed,
                "response_code": body["response_code"],
                "parser_source": body["parser_source"],
                "fallback_reason": body["fallback_reason"],
                "explanation_source": body["explanation_source"],
            }
        )

    advisor = TestClient(app).post("/conversation", json={"message": "Register me for COP 3330"}).json()
    checks.append(
        {
            "check_id": "SF-004",
            "simulation": "unsupported official action",
            "passed": advisor["response_code"] == "ADVISOR_ESCALATION_REQUIRED"
            and advisor["engine_executed"] is False
            and "register" in advisor["disclaimer"].lower(),
            "response_code": advisor["response_code"],
        }
    )

    compatibility_input = {
        "message": "Can I take COP 4331 and MAP 3305 together?",
        "student_id": "Z24567901",
        "recent_difficulty": 1,
        "satisfied_with_performance": "yes",
        "work_hours": 5,
    }
    for check_id, provider, label in (
        ("SF-005", UnsafeExplanationProvider(), "unsafe explanation proposal"),
        ("SF-006", FailingExplanationProvider(), "explanation provider timeout"),
    ):
        with patch.object(conversation_router, "_explanation_provider", provider):
            body = TestClient(app).post("/conversation", json=compatibility_input).json()
        checks.append(
            {
                "check_id": check_id,
                "simulation": label,
                "passed": body["explanation_source"] == "fallback"
                and body["explanation_fallback_used"] is True
                and "graduation guaranteed" not in body["response_text"].lower()
                and body["response_code"] == "COMPATIBILITY_EVALUATION_COMPLETE",
                "response_code": body["response_code"],
                "parser_source": body["parser_source"],
                "explanation_source": body["explanation_source"],
            }
        )

    tba = TestClient(app).post(
        "/conversation",
        json={"message": "Do CRN 18077 and CRN 20158 overlap?", "sections": ["18077", "20158"]},
    ).json()
    checks.append(
        {
            "check_id": "SF-007",
            "simulation": "committed catalog TBA timing",
            "passed": tba["response_code"] == "SCHEDULE_UNCERTAIN_TIMING"
            and "not a no-conflict result" in tba["response_text"].lower()
            and tba["engine_executed"] is True,
            "response_code": tba["response_code"],
            "parser_source": tba["parser_source"],
            "explanation_source": tba["explanation_source"],
        }
    )
    return checks


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def ratio(key: str) -> dict[str, Any]:
        numerator = sum(bool(row["scores"][key]) for row in rows)
        denominator = len(rows)
        return {
            "numerator": numerator,
            "denominator": denominator,
            "percent": round(100 * numerator / denominator, 1) if denominator else None,
        }

    associations = [row for row in rows if row["scores"]["association_applicable"]]
    entity_field_values = [
        value
        for row in rows
        for value in row["scores"]["entity_fields"].values()
    ]
    clarification_or_escalation_codes = {
        "MISSING_COURSE_CODES",
        "AMBIGUOUS_REQUEST",
        "CONTRADICTORY_SECTION_DETAILS",
        "ADVISOR_ESCALATION_REQUIRED",
    }
    clarification_or_escalation = [
        row
        for row in rows
        if clarification_or_escalation_codes.intersection(
            set(next(case["expected_endpoint"]["response_codes"] for case in load_json(CASES_PATH) if case["case_id"] == row["case_id"]))
        )
    ]
    unsafe_count = sum(row["scores"]["unsafe_outcome"] for row in rows)
    return {
        "intent_correctness": ratio("intent_correct"),
        "entity_case_exactness": ratio("entity_exact"),
        "entity_field_correctness": {
            "numerator": sum(entity_field_values),
            "denominator": len(entity_field_values),
            "percent": round(100 * sum(entity_field_values) / len(entity_field_values), 1)
            if entity_field_values
            else None,
        },
        "association_exactness": {
            "numerator": sum(row["scores"]["association_exact"] for row in associations),
            "denominator": len(associations),
            "percent": round(
                100 * sum(row["scores"]["association_exact"] for row in associations) / len(associations), 1
            )
            if associations
            else None,
        },
        "handler_correctness": ratio("handler_correct"),
        "disposition_correctness": ratio("disposition_correct"),
        "engine_behavior_correctness": ratio("engine_behavior_correct"),
        "response_code_correctness": ratio("response_code_correct"),
        "required_limitations_correctness": ratio("required_limitations_correct"),
        "clarification_escalation_correctness": {
            "numerator": sum(
                row["scores"]["response_code_correct"]
                and row["scores"]["engine_behavior_correct"]
                for row in clarification_or_escalation
            ),
            "denominator": len(clarification_or_escalation),
            "percent": round(
                100
                * sum(
                    row["scores"]["response_code_correct"]
                    and row["scores"]["engine_behavior_correct"]
                    for row in clarification_or_escalation
                )
                / len(clarification_or_escalation),
                1,
            )
            if clarification_or_escalation
            else None,
        },
        "unsafe_outcomes": {"count": unsafe_count, "denominator": len(rows)},
    }


def write_csv(
    cases: list[dict[str, Any]], results: dict[str, Any], output_path: Path
) -> None:
    by_id = {case["case_id"]: case for case in cases}
    rows = results.get("matched", {}).get("deterministic", []) + results.get("matched", {}).get("live", [])
    fields = [
        "case_id",
        "origin",
        "mode",
        "expected_intents",
        "actual_intent",
        "parser_source",
        "fallback_used",
        "fallback_reason",
        "target_handler",
        "disposition",
        "response_code",
        "engine_executed",
        "explanation_source",
        "intent_correct",
        "entity_exact",
        "association_exact",
        "handler_correct",
        "disposition_correct",
        "engine_behavior_correct",
        "required_limitations_correct",
        "unsafe_outcome",
        "latency_ms",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            case = by_id[row["case_id"]]
            parsed = row["validated_parse"]
            endpoint = row["endpoint"]
            score = row["scores"]
            writer.writerow(
                {
                    "case_id": row["case_id"],
                    "origin": case["origin"],
                    "mode": row["mode"],
                    "expected_intents": "|".join(case["expected_intents"]),
                    "actual_intent": parsed.get("intent"),
                    "parser_source": parsed.get("parser_source"),
                    "fallback_used": parsed.get("fallback_used"),
                    "fallback_reason": parsed.get("fallback_reason"),
                    "target_handler": endpoint.get("target_handler"),
                    "disposition": endpoint.get("disposition"),
                    "response_code": endpoint.get("response_code"),
                    "engine_executed": endpoint.get("engine_executed"),
                    "explanation_source": endpoint.get("explanation_source"),
                    "intent_correct": score["intent_correct"],
                    "entity_exact": score["entity_exact"],
                    "association_exact": score["association_exact"] if score["association_applicable"] else "N/A",
                    "handler_correct": score["handler_correct"],
                    "disposition_correct": score["disposition_correct"],
                    "engine_behavior_correct": score["engine_behavior_correct"],
                    "required_limitations_correct": score["required_limitations_correct"],
                    "unsafe_outcome": score["unsafe_outcome"],
                    "latency_ms": row["latency_ms"],
                }
            )


def current_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def rescore_saved_results(results: dict[str, Any], cases: list[dict[str, Any]]) -> None:
    """Recompute scores from captured validated data without another provider call."""
    case_by_id = {case["case_id"]: case for case in cases}
    matched = results.setdefault("matched", {})
    for mode in ("deterministic", "live"):
        rows = matched.get(mode, [])
        for row in rows:
            row["scores"] = score_case(
                case_by_id[row["case_id"]], row["validated_parse"], row["endpoint"]
            )
        if mode == "deterministic" and rows:
            matched["deterministic_metrics"] = aggregate(rows)
        if mode == "live" and rows:
            matched["live_metrics_all_end_to_end"] = aggregate(rows)
            valid_live = [
                row for row in rows if row["validated_parse"].get("parser_source") == "llm"
            ]
            matched["live_metrics_valid_llm_only"] = aggregate(valid_live)


def select_output_paths(
    *, live: bool, requested_output: Path | None, overwrite_live_evidence: bool
) -> tuple[Path, Path]:
    """Keep ordinary offline runs away from the canonical recorded evidence."""
    if requested_output is None:
        return (
            (RESULTS_PATH, CSV_PATH)
            if live
            else (OFFLINE_RESULTS_PATH, OFFLINE_CSV_PATH)
        )

    results_path = requested_output
    if not results_path.is_absolute():
        results_path = ROOT / results_path
    results_path = results_path.resolve()

    if (
        not live
        and results_path == RESULTS_PATH.resolve()
        and RESULTS_PATH.exists()
        and load_json(RESULTS_PATH).get("live_run")
        and not overwrite_live_evidence
    ):
        raise ValueError(
            "Offline execution cannot overwrite recorded live evidence without "
            "--overwrite-live-evidence. Omit --output to use .local-report instead."
        )

    csv_path = (
        CSV_PATH
        if results_path == RESULTS_PATH.resolve()
        else results_path.with_name(f"{results_path.stem}_comparison.csv")
    )
    return results_path, csv_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Opt in to up to 12 sequential Gemini calls.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Explicit JSON output path. Offline runs default to ignored .local-report evidence.",
    )
    parser.add_argument(
        "--overwrite-live-evidence",
        action="store_true",
        help="Explicitly allow an offline run to replace the canonical recorded live files.",
    )
    args = parser.parse_args()

    try:
        output_path, csv_path = select_output_paths(
            live=args.live,
            requested_output=args.output,
            overwrite_live_evidence=args.overwrite_live_evidence,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    cases = load_json(CASES_PATH)
    if len(cases) > MAX_LIVE_ATTEMPTS:
        raise SystemExit(f"Matched set has {len(cases)} cases; maximum is {MAX_LIVE_ATTEMPTS}.")

    existing = load_json(output_path) if output_path.exists() else {}
    results = {
        **existing,
        "schema_version": "1.0",
        "evaluated_commit": current_sha(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "case_count": len(cases),
    }

    if not args.live:
        with process_environment(CONVERSATIONAL_PARSER_MODE="deterministic"):
            deterministic_rows = [execute_case(case, "deterministic") for case in cases]
            safety = offline_safety_evaluation()
        dataset = deterministic_dataset_evaluation()
        results["deterministic_dataset"] = dataset
        results.setdefault("matched", {})["deterministic"] = deterministic_rows
        results["matched"]["deterministic_metrics"] = aggregate(deterministic_rows)
        results["offline_safety"] = {
            "total": len(safety),
            "passed": sum(row["passed"] for row in safety),
            "checks": safety,
        }
    else:
        if os.getenv("CONVERSATIONAL_PARSER_MODE") != "hybrid":
            raise SystemExit("Live mode requires process-local CONVERSATIONAL_PARSER_MODE=hybrid.")
        if os.getenv("GEMINI_MODEL") != APPROVED_LIVE_MODEL:
            raise SystemExit(f"Live mode requires GEMINI_MODEL={APPROVED_LIVE_MODEL}.")
        if not os.getenv("GEMINI_API_KEY"):
            raise SystemExit("Live mode requires the existing process-visible GEMINI_API_KEY.")
        live_rows = []
        stopped_reason = None
        attempts = 0
        for case in cases:
            attempts += 1
            row = execute_case(case, "hybrid")
            live_rows.append(row)
            fallback_reason = row["validated_parse"].get("fallback_reason") or ""
            if any(token in fallback_reason.lower() for token in ("quota", "rate limit", "authentication", "permission", "connection")):
                stopped_reason = fallback_reason
                break
        completed_ids = {row["case_id"] for row in live_rows}
        not_run = [case["case_id"] for case in cases if case["case_id"] not in completed_ids]
        valid_live = [row for row in live_rows if row["validated_parse"].get("parser_source") == "llm"]
        results.setdefault("matched", {})["live"] = live_rows
        results["matched"]["live_metrics_all_end_to_end"] = aggregate(live_rows)
        results["matched"]["live_metrics_valid_llm_only"] = aggregate(valid_live)
        deterministic_by_id = {
            row["case_id"]: row
            for row in results.get("matched", {}).get("deterministic", [])
        }
        comparable = [row for row in live_rows if row["case_id"] in deterministic_by_id]
        agreement_count = sum(
            row["validated_parse"].get("intent")
            == deterministic_by_id[row["case_id"]]["validated_parse"].get("intent")
            for row in comparable
        )
        results["live_run"] = {
            "model": APPROVED_LIVE_MODEL,
            "attempts": attempts,
            "completed": len(live_rows),
            "valid_llm_parses": len(valid_live),
            "fallbacks": len(live_rows) - len(valid_live),
            "stopped_reason": stopped_reason,
            "not_run": not_run,
            "deterministic_live_intent_agreement": {
                "numerator": agreement_count,
                "denominator": len(comparable),
                "percent": round(100 * agreement_count / len(comparable), 1)
                if comparable
                else None,
            },
        }

    # Scoring changes can be applied to captured live results without spending
    # another external attempt. This never replays a provider request.
    rescore_saved_results(results, cases)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    write_csv(cases, results, csv_path)
    print(json.dumps({
        "output": str(output_path.relative_to(ROOT)),
        "csv_output": str(csv_path.relative_to(ROOT)),
        "dataset": results.get("deterministic_dataset", {}),
        "deterministic_metrics": results.get("matched", {}).get("deterministic_metrics"),
        "live_run": results.get("live_run"),
        "offline_safety": results.get("offline_safety"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
