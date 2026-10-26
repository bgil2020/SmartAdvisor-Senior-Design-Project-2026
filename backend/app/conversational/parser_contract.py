"""Canonical Parsing Contract for Conversational Assistant.

Defines the unified, strongly-typed data structures for intent and entity
interpretation across deterministic and LLM-based parsers. Both deterministic
and Gemini parsers normalize into this canonical schema before deterministic
validation, safety gating, and backend dispatch.
"""
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field

# Canonical Intent Identifiers
INTENT_COURSE_COMPATIBILITY = "course_compatibility_check"
INTENT_SCHEDULE_CONFLICT = "schedule_conflict_check"
INTENT_ALTERNATIVE_SECTION = "alternative_section_search"
INTENT_ONLINE_OVERRIDE = "online_override_screening"
INTENT_ADVISOR_ESCALATION = "advisor_escalation"
INTENT_INFORMATIONAL_RAG = "future_rag_candidate"
INTENT_CLARIFICATION = "clarification"
INTENT_UNSUPPORTED = "unsupported_scope"

SUPPORTED_INTENTS = (
    INTENT_COURSE_COMPATIBILITY,
    INTENT_SCHEDULE_CONFLICT,
    INTENT_ALTERNATIVE_SECTION,
    INTENT_ONLINE_OVERRIDE,
    INTENT_ADVISOR_ESCALATION,
    INTENT_INFORMATIONAL_RAG,
    INTENT_CLARIFICATION,
    INTENT_UNSUPPORTED,
)


class CourseSectionPair(BaseModel):
    """Pairing of a course code and section identifier."""
    course: str = Field(..., description="Normalized course code with suffix, e.g. 'COP3530C' or 'MAC2312'")
    section: str = Field(..., description="Section number or identifier, e.g. '001', '006'")
    raw_course: Optional[str] = Field(default=None, description="Original course string as mentioned in query")


class ScheduleConstraints(BaseModel):
    """Temporal and day-of-week constraints extracted from user queries."""
    available_days: List[str] = Field(default_factory=list, description="Days user prefers, e.g. ['MON', 'WED']")
    unavailable_days: List[str] = Field(default_factory=list, description="Days user cannot attend")
    available_before: Optional[str] = Field(default=None, description="Time boundary, e.g. '12:00 PM'")
    available_after: Optional[str] = Field(default=None, description="Time boundary, e.g. '02:00 PM'")
    unavailable_before: Optional[str] = Field(default=None)
    unavailable_after: Optional[str] = Field(default=None)
    meeting_time_ranges: List[Dict[str, Any]] = Field(default_factory=list)


class CanonicalParsingResult(BaseModel):
    """The canonical parsed representation of a user query.

    Both deterministic regex and LLM parsers output this structure.
    Deterministic policy and safety logic operate strictly on this contract.
    """
    raw_message: str = Field(..., description="Original raw user input message")
    intent: str = Field(..., description="Classified intent identifier")
    course_codes: List[str] = Field(default_factory=list, description="Normalized course codes e.g. ['COP3530C']")
    section_identifiers: List[str] = Field(default_factory=list, description="Section identifiers e.g. ['001']")
    course_section_pairs: List[CourseSectionPair] = Field(default_factory=list)
    crns: List[str] = Field(default_factory=list, description="Explicit 5-digit CRNs mentioned")
    term: Optional[str | int] = Field(default=None, description="Term code e.g. 202608")
    schedule_constraints: ScheduleConstraints = Field(default_factory=ScheduleConstraints)
    modality_preference: Optional[str] = Field(default=None, description="'online', 'in_person', or None")

    # Uncertainty & Diagnostic Flags
    is_uncertain: bool = Field(default=False, description="True if interpretation is uncertain or ambiguous")
    uncertainty_reason: Optional[str] = Field(default=None)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # Observability Metadata
    parser_source: Literal["deterministic", "llm", "fallback"] = Field(
        default="deterministic",
        description="The parser that produced this result"
    )
    fallback_used: bool = Field(default=False, description="True if fallback was triggered")
    fallback_reason: Optional[str] = Field(default=None, description="Sanitized reason for fallback if used")
    model_id: Optional[str] = Field(default=None, description="Model identifier if LLM was used")

    # Fields computed deterministically post-extraction
    needs_clarification: bool = Field(default=False)
    missing_fields: List[str] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)
    matched_rules: List[str] = Field(default_factory=list)

    def to_extractor_dict(self) -> Dict[str, Any]:
        """Convert to legacy entity_extractor dict format for response policy compatibility."""
        pairs = [
            {"course": p.course, "section": p.section, "raw_course": p.raw_course or p.course}
            for p in self.course_section_pairs
        ]
        return {
            "raw_message": self.raw_message,
            "intent": self.intent,
            "matched_rules": self.matched_rules,
            "needs_clarification": self.needs_clarification,
            "reason": self.uncertainty_reason,
            "course_codes": self.course_codes,
            "section_identifiers": self.section_identifiers,
            "course_section_pairs": pairs,
            "crns": self.crns,
            "schedule_constraints": self.schedule_constraints.model_dump(),
            "modality_preference": self.modality_preference,
            "missing_fields": sorted(list(set(self.missing_fields))),
            "validation_errors": self.validation_errors,
            "parser_source": self.parser_source,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "model_id": self.model_id,
        }
