"""Hybrid Conversational Parser Dispatcher.

Orchestrates deterministic and LLM-based intent/entity parsing:
- Default mode: 'deterministic' (100% offline rule-based).
- 'hybrid' mode: attempts Gemini structured output first with local grounding validation;
  automatically and gracefully falls back to deterministic parsing upon any provider failure,
  timeout, missing key, quota exhaustion, or schema validation error.

Never exposes raw secrets or provider error stack traces in user responses.
"""
import concurrent.futures
import logging
import os
import time
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

try:
    from backend.app.conversational.parser_contract import (
        CanonicalParsingResult,
        CourseSectionPair,
        ScheduleConstraints,
        INTENT_CLARIFICATION,
    )
    from backend.app.conversational.entity_extractor import extract_entities
    from backend.app.conversational.gemini_parser import (
        GeminiStructuredParser,
        DEFAULT_GEMINI_MODEL,
        DEFAULT_GEMINI_TIMEOUT,
    )
except ImportError:
    from app.conversational.parser_contract import (
        CanonicalParsingResult,
        CourseSectionPair,
        ScheduleConstraints,
        INTENT_CLARIFICATION,
    )
    from app.conversational.entity_extractor import extract_entities
    from app.conversational.gemini_parser import (
        GeminiStructuredParser,
        DEFAULT_GEMINI_MODEL,
        DEFAULT_GEMINI_TIMEOUT,
    )

logger = logging.getLogger(__name__)

MODE_DETERMINISTIC = "deterministic"
MODE_HYBRID = "hybrid"


def get_parser_mode() -> str:
    """Retrieve current parser mode from environment, defaulting to deterministic."""
    mode = os.getenv("CONVERSATIONAL_PARSER_MODE", MODE_DETERMINISTIC).strip().lower()
    return mode if mode in (MODE_DETERMINISTIC, MODE_HYBRID) else MODE_DETERMINISTIC


def is_gemini_configured() -> bool:
    """Check if Gemini API key is configured without exposing key value."""
    key = os.getenv("GEMINI_API_KEY")
    return bool(key and key.strip())


def parse_deterministic(message: str) -> CanonicalParsingResult:
    """Execute the established deterministic rule-based classifier and entity extractor."""
    res = extract_entities(message)
    pairs = [
        CourseSectionPair(
            course=p["course"],
            section=p["section"],
            raw_course=p.get("raw_course", p["course"]),
        )
        for p in res.get("course_section_pairs", [])
    ]
    constraints_dict = res.get("schedule_constraints", {})
    constraints = ScheduleConstraints(**constraints_dict) if constraints_dict else ScheduleConstraints()

    return CanonicalParsingResult(
        raw_message=message,
        intent=res["intent"],
        course_codes=res["course_codes"],
        section_identifiers=res["section_identifiers"],
        course_section_pairs=pairs,
        crns=res["crns"],
        schedule_constraints=constraints,
        modality_preference=res.get("modality_preference"),
        is_uncertain=res.get("needs_clarification", False) and res.get("intent") == INTENT_CLARIFICATION,
        uncertainty_reason=res.get("reason"),
        parser_source="deterministic",
        fallback_used=False,
        needs_clarification=res.get("needs_clarification", False),
        missing_fields=res.get("missing_fields", []),
        validation_errors=res.get("validation_errors", []),
        matched_rules=res.get("matched_rules", []),
    )


class HybridConversationalParser:
    """Coordinates hybrid parsing with deterministic fallback."""

    def __init__(
        self,
        gemini_parser: Optional[GeminiStructuredParser] = None,
        force_mode: Optional[str] = None,
    ):
        self.gemini_parser = gemini_parser
        self.force_mode = force_mode

    def parse(self, message: str, context: Optional[Dict[str, Any]] = None) -> CanonicalParsingResult:
        """Parse query using active mode with automatic deterministic fallback."""
        mode = self.force_mode or get_parser_mode()

        if mode != MODE_HYBRID:
            return parse_deterministic(message)

        # Hybrid mode active: Verify configuration
        model_name = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        if not is_gemini_configured() and not (self.gemini_parser and self.gemini_parser._client):
            logger.info("Hybrid mode requested but GEMINI_API_KEY is not configured; executing deterministic fallback.")
            fallback_res = parse_deterministic(message)
            fallback_res.parser_source = "fallback"
            fallback_res.fallback_used = True
            fallback_res.fallback_reason = "GEMINI_API_KEY not configured"
            fallback_res.model_id = model_name
            return fallback_res

        # Attempt Gemini structured parsing
        parser = self.gemini_parser or GeminiStructuredParser()
        start_time = time.time()
        try:
            llm_result = parser.parse(message, context=context)
            duration_ms = (time.time() - start_time) * 1000
            logger.info("Gemini structured parsing succeeded in %.1f ms (model=%s)", duration_ms, model_name)
            return llm_result

        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            sanitized_reason = self._sanitize_fallback_reason(exc)
            logger.warning(
                "Gemini parsing failed after %.1f ms (%s); falling back to deterministic parser.",
                duration_ms,
                sanitized_reason,
            )
            fallback_res = parse_deterministic(message)
            fallback_res.parser_source = "fallback"
            fallback_res.fallback_used = True
            fallback_res.fallback_reason = sanitized_reason
            fallback_res.model_id = model_name
            return fallback_res

    def _sanitize_fallback_reason(self, exc: Exception) -> str:
        """Sanitize error message to prevent leaking keys, raw URLs, or server paths."""
        err_type = type(exc).__name__
        err_str = str(exc).lower()

        if isinstance(exc, (TimeoutError, concurrent.futures.TimeoutError)) or "timeout" in err_type.lower() or "timeout" in err_str or "timed out" in err_str:
            return "Provider request timed out"
        if "quota" in err_str or "429" in err_str or "402" in err_str or "rate limit" in err_str or "resource_exhausted" in err_str or "resourceexhausted" in err_type.lower():
            return "Provider rate limit or quota exceeded"
        if "auth" in err_str or "api_key" in err_str or "permission" in err_str or "403" in err_str or "permissiondenied" in err_type.lower():
            return "Provider authentication or permission error"
        if "validation" in err_str or "schema" in err_str or "validationerror" in err_type.lower():
            return "Model output failed schema validation"
        if "ungrounded" in err_str or "invented" in err_str:
            return "Model output contained ungrounded or invented entities"
        if "empty" in err_str:
            return "Model returned empty response"

        return f"Provider error ({err_type})"


# Default module-level singleton instance
_default_dispatcher = HybridConversationalParser()


def parse_query(message: str, context: Optional[Dict[str, Any]] = None) -> CanonicalParsingResult:
    """Primary entry point for conversational parsing with deterministic fallback."""
    return _default_dispatcher.parse(message, context=context)
