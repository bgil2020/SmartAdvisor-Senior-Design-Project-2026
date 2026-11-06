import asyncio
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Literal
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

try:
    from backend.app.conversational.response_policy import (
        build_conversation_response,
        DISPOSITION_ROUTE_CORE,
        DISPOSITION_CLARIFY,
        DISPOSITION_ESCALATION,
        DISPOSITION_RAG,
        DISPOSITION_UNSUPPORTED,
        HANDLER_COMPATIBILITY,
        HANDLER_SCHEDULING,
        HANDLER_OVERRIDE,
        reconcile_informational_scope,
    )
    from backend.app.conversational.intent_classifier import (
        SCHEDULE_CONFLICT,
        ALTERNATIVE_SECTION,
    )
    from backend.app.conversational.hybrid_parser import parse_query
    from backend.app.conversational.explanation_contract import (
        BaseExplanationProvider,
        DEFAULT_EXPLANATION_DISCLAIMER,
        EXPLANATION_CONTRACT_VERSION,
        render_explanation,
    )
except ImportError:
    from app.conversational.response_policy import (
        build_conversation_response,
        DISPOSITION_ROUTE_CORE,
        DISPOSITION_CLARIFY,
        DISPOSITION_ESCALATION,
        DISPOSITION_RAG,
        DISPOSITION_UNSUPPORTED,
        HANDLER_COMPATIBILITY,
        HANDLER_SCHEDULING,
        HANDLER_OVERRIDE,
        reconcile_informational_scope,
    )
    from app.conversational.intent_classifier import (
        SCHEDULE_CONFLICT,
        ALTERNATIVE_SECTION,
    )
    from app.conversational.hybrid_parser import parse_query
    from app.conversational.explanation_contract import (
        BaseExplanationProvider,
        DEFAULT_EXPLANATION_DISCLAIMER,
        EXPLANATION_CONTRACT_VERSION,
        render_explanation,
    )

from .compatibility_engine import evaluate_compatibility
from .scheduling_service import (
    get_course_catalog,
    resolve_section,
    normalize_course_code,
    evaluate_schedule_conflict,
    evaluate_alternative_sections,
)
from .rag.service import answer_information_question
from .rag.catalog_acquisition import (
    CatalogAcquisitionResult,
    CatalogAcquisitionSettings,
    get_catalog_acquisition_coordinator,
)
from .rag.operational_storage import OperationalStorageError, default_operational_root, get_runtime_store
from .rag.syllabus_acquisition import (
    SyllabusAcquisitionSettings,
    get_syllabus_acquisition_coordinator,
)

router = APIRouter(tags=["Conversational Assistant"])

# Deterministic rendering is the production default. Tests may replace this
# seam with fake providers; no live explanation provider is enabled.
_explanation_provider: BaseExplanationProvider | None = None


class ConversationRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500, description="Student user query message")
    student_id: str | None = Field(default=None, description="Synthetic student identifier (e.g., Z24567901)")
    recent_difficulty: int | None = Field(default=None, ge=1, le=5, description="Difficulty rating 1 to 5")
    satisfied_with_performance: Literal["yes", "mostly", "no"] | None = Field(
        default=None, description="Satisfaction with past semester performance"
    )
    work_hours: float | None = Field(default=None, ge=0, le=80, description="Hours worked per week")
    preferred_max_credits: float | None = Field(default=None, ge=1, le=30, description="Max target credits")
    recent_courses: list[str] | None = Field(default=None, description="Previously completed recent course codes")
    course_code: str | None = Field(default=None, description="Optional explicit course scope for an informational RAG request")
    term: int | str | None = Field(default=None, description="Term code for section lookups, e.g. 202608")
    section: str | None = Field(default=None, description="Optional syllabus section filter, e.g. 001")
    sections: list[Any] | None = Field(
        default=None, description="Explicit list of sections to compare (CRNs or course+section dicts)"
    )
    target_section: Any | None = Field(
        default=None, description="Target section to replace in alternative section search"
    )
    selected_sections: list[Any] | None = Field(
        default=None, description="Enrolled/selected schedule sections to avoid conflicts with"
    )


class ConversationResponse(BaseModel):
    status: Literal[
        "engine_executed",
        "clarification",
        "escalation",
        "rag_inactive",
        "rag_answered",
        "no_relevant_evidence",
        "unsupported",
        "engine_unavailable",
        "engine_error",
    ]
    raw_message: str
    disposition: str
    target_handler: str
    response_code: str
    response_text: str
    actionable_guidance: str | None = None
    safe_to_route: bool
    missing_context: list[str] = Field(default_factory=list)
    extracted_courses: list[str] = Field(default_factory=list)
    engine_executed: bool = False
    engine_result: dict | None = None
    disclaimer: str = DEFAULT_EXPLANATION_DISCLAIMER
    # Observability metadata
    parser_source: Literal["deterministic", "llm", "fallback"] = "deterministic"
    fallback_used: bool = False
    fallback_reason: str | None = None
    model_id: str | None = None
    explanation_source: Literal["deterministic", "provider_structured", "fallback"] = "deterministic"
    explanation_fallback_used: bool = False
    explanation_fallback_reason: str | None = None
    explanation_contract_version: str = EXPLANATION_CONTRACT_VERSION
    evidence_references: list[str] = Field(default_factory=list)
    explanation_limitations: list[str] = Field(default_factory=list)
    rag_executed: bool = False
    generation_source: Literal["provider", "source_excerpt_fallback", "none"] | None = None
    generation_fallback_used: bool = False
    generation_fallback_reason: str | None = None
    rag_sources: list[dict] = Field(default_factory=list)
    retrieved_evidence_count: int = 0
    evidence_decision: str | None = None
    evidence_reason: str | None = None
    resolved_scope: dict[str, str | None] = Field(default_factory=dict)
    required_source_categories: list[str] = Field(default_factory=list)
    supporting_source_ids: list[str] = Field(default_factory=list)
    missing_evidence_categories: list[str] = Field(default_factory=list)
    acquisition_eligible: bool = False
    acquisition_plan: dict | None = None
    initial_evidence_decision: str | None = None
    initial_acquisition_plan: dict | None = None
    acquisition_enabled: bool = False
    acquisition_attempted: bool = False
    acquisition_outcome: str | None = None
    acquisition_reason: str | None = None
    acquisition_coalesced: bool = False
    acquisition_request_count: int = 0
    acquisition_redirect_count: int = 0
    acquisition_retry_count: int = 0
    acquisition_document_id: str | None = None
    acquisition_stop_reason: str | None = None
    acquisition_browser_response_count: int = 0
    acquisition_essential_request_count: int = 0
    acquisition_diagnostic_id: str | None = None
    post_acquisition_evidence_decision: str | None = None
    active_corpus_generation: str | None = None


def _handle_conversation_sync(
    req: ConversationRequest,
    cancellation: threading.Event | None = None,
) -> ConversationResponse:
    """
    Evaluates student prompt using conversational parser (deterministic or hybrid Gemini)
    and deterministic response policy.
    When intent is course compatibility or scheduling and full context is supplied,
    executes the authoritative core engines directly.
    """
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # Execute parser (hybrid with automatic fallback, or deterministic)
    parsed_result = parse_query(message, context=req.model_dump())
    policy_resp = build_conversation_response(message, parsed_result=parsed_result)

    disposition = policy_resp.get("disposition")
    target_handler = policy_resp.get("target_handler")
    response_code = policy_resp.get("response_code", "UNKNOWN")
    response_text = policy_resp.get("response_text", "")
    entities = policy_resp.get("entities", {})
    extracted_courses = entities.get("course_codes", [])

    parser_source = entities.get("parser_source", "deterministic")
    fallback_used = entities.get("fallback_used", False)
    fallback_reason = entities.get("fallback_reason")
    model_id = entities.get("model_id")

    def _build_response(**kwargs) -> ConversationResponse:
        kwargs.setdefault("parser_source", parser_source)
        kwargs.setdefault("fallback_used", fallback_used)
        kwargs.setdefault("fallback_reason", fallback_reason)
        kwargs.setdefault("model_id", model_id)
        explanation = render_explanation(
            response_code=kwargs.get("response_code", "UNKNOWN"),
            target_handler=kwargs.get("target_handler", "none"),
            current_text=kwargs.get("response_text", ""),
            engine_result=kwargs.get("engine_result"),
            extracted_courses=kwargs.get("extracted_courses", []),
            missing_context=kwargs.get("missing_context", []),
            provider=_explanation_provider,
        )
        kwargs["response_text"] = explanation.response_text
        kwargs["disclaimer"] = explanation.disclaimer
        kwargs["explanation_source"] = explanation.explanation_source
        kwargs["explanation_fallback_used"] = explanation.explanation_fallback_used
        kwargs["explanation_fallback_reason"] = explanation.explanation_fallback_reason
        kwargs["explanation_contract_version"] = explanation.contract_version
        kwargs["evidence_references"] = explanation.evidence_references
        kwargs["explanation_limitations"] = explanation.limitations
        return ConversationResponse(**kwargs)

    # 1. Escalation to advisor
    if disposition == DISPOSITION_ESCALATION:
        return _build_response(
            status="escalation",
            raw_message=message,
            disposition=disposition,
            target_handler=target_handler,
            response_code=response_code,
            response_text=response_text,
            actionable_guidance="Official advising actions (overrides, registration, graduation) require consulting with an authorized academic advisor.",
            safe_to_route=False,
            engine_executed=False,
            extracted_courses=extracted_courses,
        )

    # 2. Informational RAG queries. Retrieval is local; fetching/importing is a
    # separate explicit workflow and never occurs while serving a question.
    if disposition == DISPOSITION_RAG:
        scope = reconcile_informational_scope(
            entities,
            explicit_course_code=req.course_code,
            explicit_term=req.term,
            explicit_section=req.section,
        )
        if scope["conflicts"] or scope["ambiguity"]:
            issue = scope["conflicts"] or scope["ambiguity"]
            return ConversationResponse(
                status="clarification",
                raw_message=message,
                disposition=disposition,
                target_handler=target_handler,
                response_code="RAG_CLARIFICATION",
                response_text=f"Please resolve the conflicting or ambiguous informational scope: {', '.join(issue)}.",
                actionable_guidance="Provide one consistent course, term, and section through the message and explicit request fields.",
                safe_to_route=False,
                missing_context=["consistent_informational_scope"],
                extracted_courses=extracted_courses,
                parser_source=parser_source,
                fallback_used=fallback_used,
                fallback_reason=fallback_reason,
                model_id=model_id,
                rag_executed=True,
                generation_source="none",
                evidence_decision="conflicting_scope",
                evidence_reason="Parsed and explicit scope conflict or contain multiple identities.",
                resolved_scope={key: scope[key] for key in ("course_code", "term_id", "section")},
                acquisition_eligible=False,
                acquisition_plan={
                    "execute": False,
                    "eligible": False,
                    "evidence_gap": "conflicting_scope",
                    "collector_capability": "No acquisition should run until scope is consistent.",
                    "clarification_required": True,
                    "manual_action_required": True,
                    "course_code": scope["course_code"],
                    "source_categories": [],
                    "term_id": scope["term_id"],
                    "section": scope["section"],
                },
            )
        rag = answer_information_question(
            message,
            course_codes=[scope["course_code"]] if scope["course_code"] else [],
            term_id=scope["term_id"],
            section=scope["section"],
        )
        initial_evidence_decision = rag.evidence_decision
        initial_acquisition_plan = rag.acquisition_plan.model_dump() if rag.acquisition_plan else None
        catalog_settings = CatalogAcquisitionSettings.from_environment()
        syllabus_settings = SyllabusAcquisitionSettings.from_environment()
        initial_categories = rag.required_source_categories
        acquisition_enabled = (
            catalog_settings.enabled if initial_categories == ["course_description"]
            else syllabus_settings.enabled if initial_categories == ["syllabus"]
            else False
        )
        acquisition = CatalogAcquisitionResult(
            outcome="not_needed" if rag.status == "answered" else "not_eligible",
            course_code=scope["course_code"],
            reason=(
                "Local evidence already supports the request."
                if rag.status == "answered"
                else "The readiness result is not eligible for this bounded catalog executor."
            ),
        )
        runtime_store = None
        storage_error: str | None = None
        if os.getenv("RAG_OPERATIONAL_ROOT"):
            try:
                runtime_store = get_runtime_store(default_operational_root(Path(__file__).resolve().parents[1]))
            except OperationalStorageError as exc:
                storage_error = f"Operational storage could not be loaded ({type(exc).__name__})."
        if acquisition_enabled and rag.evidence_decision == "corpus_unavailable":
            if storage_error is not None:
                acquisition = CatalogAcquisitionResult("storage_unusable", scope["course_code"], reason=storage_error)
            elif runtime_store is None:
                acquisition = CatalogAcquisitionResult(
                    "storage_not_configured", scope["course_code"],
                    reason="RAG_OPERATIONAL_ROOT must identify initialized operational storage before acquisition.",
                )
            elif runtime_store.snapshot() is None:
                acquisition = CatalogAcquisitionResult(
                    "storage_uninitialized", scope["course_code"],
                    reason="Initialize operational storage explicitly before acquisition.",
                )
            else:
                acquisition = CatalogAcquisitionResult(
                    "storage_recovery_required", scope["course_code"],
                    reason="Repair the operational generation before acquisition.",
                )
        elif rag.status != "answered" and rag.acquisition_plan is not None and rag.acquisition_eligible:
            if not acquisition_enabled:
                acquisition = CatalogAcquisitionResult(
                    "disabled", scope["course_code"], reason="The required source acquisition path is opt-in and disabled."
                )
            elif storage_error is not None:
                acquisition = CatalogAcquisitionResult(
                    "storage_unusable", scope["course_code"], reason=storage_error
                )
            elif runtime_store is None:
                acquisition = CatalogAcquisitionResult(
                    "storage_not_configured", scope["course_code"],
                    reason="RAG_OPERATIONAL_ROOT must identify initialized operational storage before acquisition.",
                )
            else:
                if rag.acquisition_plan.source_categories == ["course_description"]:
                    catalog = get_course_catalog()
                    supported_courses = {
                        normalize_course_code(value)
                        for value in catalog["COURSE"].dropna().astype(str).tolist()
                    }
                    acquisition = get_catalog_acquisition_coordinator(catalog_settings).execute(
                        rag.acquisition_plan,
                        runtime_store=runtime_store,
                        supported_courses=supported_courses,
                        cancelled=cancellation,
                    )
                elif rag.acquisition_plan.source_categories == ["syllabus"]:
                    acquisition = get_syllabus_acquisition_coordinator(syllabus_settings).execute(
                        rag.acquisition_plan,
                        runtime_store=runtime_store,
                        cancelled=cancellation,
                    )
                else:
                    acquisition = CatalogAcquisitionResult(
                        "unsupported_mixed_plan", scope["course_code"],
                        reason="This increment executes only one catalog or one exact-mapping syllabus source.",
                    )
                if acquisition.outcome in {"published", "unchanged", "local_evidence_available"}:
                    # Exactly one post-publication readiness/retrieval attempt.
                    rag = answer_information_question(
                        message,
                        course_codes=[scope["course_code"]] if scope["course_code"] else [],
                        term_id=scope["term_id"],
                        section=scope["section"],
                    )
        active_generation = None
        if runtime_store is not None:
            active_snapshot = runtime_store.snapshot()
            active_generation = active_snapshot.generation_id if active_snapshot else None
        status = {
            "answered": "rag_answered",
            "clarification": "clarification",
            "no_relevant_evidence": "no_relevant_evidence",
        }[rag.status]
        return ConversationResponse(
            status=status,
            raw_message=message,
            disposition=disposition,
            target_handler=target_handler,
            response_code={"answered": "RAG_ANSWERED", "clarification": "RAG_CLARIFICATION", "no_relevant_evidence": "RAG_NO_RELEVANT_EVIDENCE"}[rag.status],
            response_text=rag.answer,
            actionable_guidance=None if rag.status == "answered" else "Name a covered course or rebuild the local corpus with an applicable validated source.",
            safe_to_route=rag.status == "answered",
            engine_executed=False,
            extracted_courses=extracted_courses,
            parser_source=parser_source,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            model_id=rag.model_id or model_id,
            rag_executed=True,
            generation_source=rag.generation_source,
            generation_fallback_used=rag.generation_fallback_used,
            generation_fallback_reason=rag.generation_fallback_reason,
            rag_sources=rag.sources,
            retrieved_evidence_count=len(rag.retrieved_evidence),
            explanation_limitations=rag.limitations,
            evidence_decision=rag.evidence_decision,
            evidence_reason=rag.evidence_reason,
            resolved_scope=rag.resolved_scope,
            required_source_categories=rag.required_source_categories,
            supporting_source_ids=rag.supporting_source_ids,
            missing_evidence_categories=rag.missing_evidence_categories,
            acquisition_eligible=rag.acquisition_eligible,
            acquisition_plan=rag.acquisition_plan.model_dump() if rag.acquisition_plan else None,
            initial_evidence_decision=initial_evidence_decision,
            initial_acquisition_plan=initial_acquisition_plan,
            acquisition_enabled=acquisition_enabled,
            acquisition_attempted=acquisition.attempted,
            acquisition_outcome=acquisition.outcome,
            acquisition_reason=acquisition.reason,
            acquisition_coalesced=acquisition.coalesced,
            acquisition_request_count=acquisition.request_count,
            acquisition_redirect_count=acquisition.redirect_count,
            acquisition_retry_count=acquisition.retry_count,
            acquisition_document_id=acquisition.document_id,
            acquisition_stop_reason=acquisition.stop_reason,
            acquisition_browser_response_count=acquisition.browser_response_count,
            acquisition_essential_request_count=acquisition.essential_request_count,
            acquisition_diagnostic_id=acquisition.diagnostic_id,
            post_acquisition_evidence_decision=rag.evidence_decision,
            active_corpus_generation=active_generation,
        )

    # 3. Allow structured context to fill missing message details (do not require text to repeat valid context)
    intent = policy_resp.get("intent")
    if disposition == DISPOSITION_CLARIFY:
        if intent == SCHEDULE_CONFLICT and req.sections and len(req.sections) >= 2:
            disposition = DISPOSITION_ROUTE_CORE
            target_handler = HANDLER_SCHEDULING
        elif intent == ALTERNATIVE_SECTION and (req.target_section or (req.sections and len(req.sections) >= 1)):
            disposition = DISPOSITION_ROUTE_CORE
            target_handler = HANDLER_SCHEDULING

    # Clarification requested by response policy
    if disposition == DISPOSITION_CLARIFY:
        return _build_response(
            status="clarification",
            raw_message=message,
            disposition=disposition,
            target_handler=target_handler,
            response_code=response_code,
            response_text=response_text,
            actionable_guidance="Please refine your message with specific course codes or choose one clear goal.",
            safe_to_route=False,
            engine_executed=False,
            extracted_courses=extracted_courses,
        )

    # 4. Unsupported queries
    if disposition == DISPOSITION_UNSUPPORTED:
        return _build_response(
            status="unsupported",
            raw_message=message,
            disposition=disposition,
            target_handler=target_handler,
            response_code=response_code,
            response_text=response_text,
            actionable_guidance="Supported topics include course workload compatibility, schedule conflict checking, and online override screening.",
            safe_to_route=False,
            engine_executed=False,
            extracted_courses=extracted_courses,
        )

    # 5. Core Engine Routing
    if disposition == DISPOSITION_ROUTE_CORE:
        # A. Course Compatibility Engine Handoff
        if target_handler == HANDLER_COMPATIBILITY:
            # Check required student workload context
            missing_context = []
            if not req.student_id:
                missing_context.append("student_id")
            if req.recent_difficulty is None:
                missing_context.append("recent_difficulty")
            if req.satisfied_with_performance is None:
                missing_context.append("satisfied_with_performance")
            if req.work_hours is None:
                missing_context.append("work_hours")

            if missing_context:
                missing_str = ", ".join(missing_context)
                return _build_response(
                    status="clarification",
                    raw_message=message,
                    disposition=disposition,
                    target_handler=target_handler,
                    response_code="MISSING_STUDENT_CONTEXT",
                    response_text=(
                        f"Compatibility request recognized for courses: {', '.join(extracted_courses)}. "
                        f"To evaluate workload compatibility, additional student workload context is required ({missing_str})."
                    ),
                    actionable_guidance=(
                        "Please select a synthetic student profile and verify workload details "
                        "in the context controls before submitting."
                    ),
                    safe_to_route=True,
                    missing_context=missing_context,
                    extracted_courses=extracted_courses,
                    engine_executed=False,
                )

            # Context is complete -> Execute compatibility engine directly
            try:
                engine_output = evaluate_compatibility(
                    student_id=req.student_id,
                    proposed_courses=extracted_courses,
                    recent_difficulty=req.recent_difficulty,
                    satisfied_with_performance=req.satisfied_with_performance,
                    work_hours=req.work_hours,
                    preferred_max_credits=req.preferred_max_credits,
                    recent_courses=req.recent_courses,
                )
            except Exception as exc:
                logger.error(
                    "Compatibility evaluation failed with exception type %s.",
                    type(exc).__name__,
                )
                return _build_response(
                    status="engine_error",
                    raw_message=message,
                    disposition=disposition,
                    target_handler=target_handler,
                    response_code="ENGINE_EXECUTION_ERROR",
                    response_text="Compatibility engine encountered an internal error.",
                    safe_to_route=True,
                    extracted_courses=extracted_courses,
                    engine_executed=True,
                    engine_result={"error": "Internal compatibility engine error"},
                )

            if not engine_output.get("success"):
                return _build_response(
                    status="engine_error",
                    raw_message=message,
                    disposition=disposition,
                    target_handler=target_handler,
                    response_code="ENGINE_EVALUATION_FAILED",
                    response_text="Compatibility evaluation could not be completed for the requested courses.",
                    safe_to_route=True,
                    extracted_courses=extracted_courses,
                    engine_executed=True,
                    engine_result=engine_output,
                )

            assessment_summary = engine_output.get("assessment", "Assessment complete")
            return _build_response(
                status="engine_executed",
                raw_message=message,
                disposition=disposition,
                target_handler=target_handler,
                response_code="COMPATIBILITY_EVALUATION_COMPLETE",
                response_text=(
                    f"Workload compatibility evaluation completed for {', '.join(extracted_courses)}. "
                    f"Semester assessment: {assessment_summary}."
                ),
                safe_to_route=True,
                extracted_courses=extracted_courses,
                engine_executed=True,
                engine_result=engine_output,
            )

        # B. Scheduling Engine (conflict / alternative)
        if target_handler == HANDLER_SCHEDULING:
            intent = policy_resp.get("intent")
            courses_catalog = get_course_catalog()

            # Helper for detecting unsupported user preferences in prompt
            unsupported_prefs = []
            if re.search(r'\b(with\s+(?:prof|professor|dr)|taught\s+by|instructor)\b', message, re.IGNORECASE):
                unsupported_prefs.append("instructor preference")
            if re.search(r'\b(morning|afternoon|evening|night)\b', message, re.IGNORECASE):
                unsupported_prefs.append("time-of-day preference")
            if re.search(r'\b(online\s+only|in[- ]person\s+only)\b', message, re.IGNORECASE):
                unsupported_prefs.append("modality preference")

            pref_note = (
                f" (Note: Requested preference [{', '.join(unsupported_prefs)}] is not filtered by this prototype; "
                f"results reflect schedule conflict and seat availability only.)"
            ) if unsupported_prefs else ""

            msg_pairs = entities.get("course_section_pairs", [])
            msg_crns = entities.get("crns", [])

            # --- B1. Schedule Conflict Check ---
            if intent == SCHEDULE_CONFLICT:
                # 1. Prevent silent truncation: Reject or clarify requests containing >2 section references
                if req.sections and len(req.sections) > 2:
                    return _build_response(
                        status="clarification",
                        raw_message=message,
                        disposition=disposition,
                        target_handler=target_handler,
                        response_code="EXCESS_SECTIONS_DETECTED",
                        response_text=(
                            f"Schedule conflict checking currently supports comparing exactly two sections at a time. "
                            f"You provided {len(req.sections)} sections ({', '.join(str(s) for s in req.sections)}). "
                            f"Please specify exactly two sections to check for conflicts."
                        ),
                        actionable_guidance="Narrow your request to exactly two sections.",
                        safe_to_route=True,
                        missing_context=["two_sections_only"],
                        extracted_courses=extracted_courses,
                        engine_executed=False,
                    )

                if (not req.sections or len(req.sections) <= 2) and (len(msg_pairs) > 2 or len(msg_crns) > 2):
                    count = max(len(msg_pairs), len(msg_crns))
                    return _build_response(
                        status="clarification",
                        raw_message=message,
                        disposition=disposition,
                        target_handler=target_handler,
                        response_code="EXCESS_SECTIONS_DETECTED",
                        response_text=(
                            f"Schedule conflict checking currently supports comparing exactly two sections at a time. "
                            f"Your query references {count} sections. "
                            f"Please specify exactly two sections to check for conflicts."
                        ),
                        actionable_guidance="Narrow your request to exactly two sections.",
                        safe_to_route=True,
                        missing_context=["two_sections_only"],
                        extracted_courses=extracted_courses,
                        engine_executed=False,
                    )

                sec1_input = None
                sec2_input = None

                # Check explicit structured sections in request
                if req.sections and len(req.sections) == 2:
                    sec1_input = req.sections[0]
                    sec2_input = req.sections[1]

                    # Cross-check structured sections against explicit message references for contradictions
                    s1_res, s1_err, _ = resolve_section(courses_catalog, sec1_input, req.term)
                    s2_res, s2_err, _ = resolve_section(courses_catalog, sec2_input, req.term)

                    if not s1_err and not s2_err:
                        s_crns = {str(s1_res["CRN"]).replace(".0", ""), str(s2_res["CRN"]).replace(".0", "")}

                        # Check if message explicitly mentions conflicting CRNs
                        if msg_crns:
                            contradictory_crns = [c for c in msg_crns if c not in s_crns]
                            if contradictory_crns:
                                return _build_response(
                                    status="clarification",
                                    raw_message=message,
                                    disposition=disposition,
                                    target_handler=target_handler,
                                    response_code="CONTRADICTORY_SECTION_DETAILS",
                                    response_text=(
                                        f"Contradictory section information detected: Message references CRN {', '.join(contradictory_crns)}, "
                                        f"which does not match structured sections ({', '.join(s_crns)}). "
                                        f"Please clarify which sections you wish to check."
                                    ),
                                    actionable_guidance="Resolve the mismatch between your message CRNs and structured sections.",
                                    safe_to_route=True,
                                    missing_context=["consistent_sections"],
                                    extracted_courses=extracted_courses,
                                    engine_executed=False,
                                )

                        # Check if message explicitly mentions conflicting course-section pairs
                        if msg_pairs:
                            for p in msg_pairs:
                                p_code = normalize_course_code(p["course"])
                                p_sec = str(p["section"]).strip().upper().lstrip("0")
                                matched = [s for s in [s1_res, s2_res] if normalize_course_code(s["COURSE"]) == p_code]
                                if matched:
                                    struct_sec = str(matched[0]["SECT"]).strip().upper().lstrip("0")
                                    if p_sec != struct_sec:
                                        return _build_response(
                                            status="clarification",
                                            raw_message=message,
                                            disposition=disposition,
                                            target_handler=target_handler,
                                            response_code="CONTRADICTORY_SECTION_DETAILS",
                                            response_text=(
                                                f"Contradictory section information detected: Message references {p['course']} section {p['section']}, "
                                                f"but structured input specifies section {matched[0]['SECT']} (CRN {str(matched[0]['CRN']).replace('.0', '')}). "
                                                f"Please clarify which section you want to evaluate."
                                            ),
                                            actionable_guidance="Resolve the mismatch between message text and structured section context.",
                                            safe_to_route=True,
                                            missing_context=["consistent_sections"],
                                            extracted_courses=extracted_courses,
                                            engine_executed=False,
                                        )
                                elif len(msg_pairs) >= 2:
                                    return _build_response(
                                        status="clarification",
                                        raw_message=message,
                                        disposition=disposition,
                                        target_handler=target_handler,
                                        response_code="CONTRADICTORY_SECTION_DETAILS",
                                        response_text=(
                                            f"Contradictory course information detected: Message references course {p['course']}, "
                                            f"which does not match structured courses ({s1_res['COURSE']}, {s2_res['COURSE']}). "
                                            f"Please clarify which courses you want to evaluate."
                                        ),
                                        actionable_guidance="Ensure message text and structured sections reference the same courses.",
                                        safe_to_route=True,
                                        missing_context=["consistent_sections"],
                                        extracted_courses=extracted_courses,
                                        engine_executed=False,
                                    )

                # Check bound course-section pairs extracted from message
                elif len(msg_pairs) == 2:
                    sec1_input = msg_pairs[0]
                    sec2_input = msg_pairs[1]
                # Check CRNs extracted from message
                elif len(msg_crns) == 2:
                    sec1_input = msg_crns[0]
                    sec2_input = msg_crns[1]

                # Check if sections are missing
                if not sec1_input or not sec2_input:
                    missing_parts = []
                    if len(extracted_courses) < 2 and len(msg_crns) < 2:
                        missing_parts.append("two courses")
                    if not msg_pairs and not msg_crns:
                        missing_parts.append("specific section numbers or CRNs")

                    detail_msg = f" ({', '.join(missing_parts)})" if missing_parts else ""
                    return _build_response(
                        status="clarification",
                        raw_message=message,
                        disposition=disposition,
                        target_handler=target_handler,
                        response_code="MISSING_SECTION_DETAILS",
                        response_text=(
                            f"To check for schedule conflicts, please provide the specific section numbers or CRNs "
                            f"for both courses{detail_msg} (e.g. 'Do COP 3530C section 001 and MAC 2312 section 006 overlap?')."
                        ),
                        actionable_guidance="Provide course codes along with section numbers or CRNs.",
                        safe_to_route=True,
                        missing_context=["section_identifiers"],
                        extracted_courses=extracted_courses,
                        engine_executed=False,
                    )

                # Attempt resolution and conflict calculation
                try:
                    conflict_res = evaluate_schedule_conflict(
                        courses=courses_catalog,
                        section1_input=sec1_input,
                        section2_input=sec2_input,
                        term=req.term,
                    )
                except Exception as exc:
                    logger.error(
                        "Conflict evaluation failed with exception type %s.",
                        type(exc).__name__,
                    )
                    return _build_response(
                        status="engine_error",
                        raw_message=message,
                        disposition=disposition,
                        target_handler=target_handler,
                        response_code="ENGINE_EXECUTION_ERROR",
                        response_text="An internal error occurred while evaluating schedule conflicts.",
                        safe_to_route=True,
                        extracted_courses=extracted_courses,
                        engine_executed=False,
                        engine_result={"error": "Internal scheduling engine error"},
                    )

                if not conflict_res.get("success"):
                    is_ambiguous = conflict_res.get("is_ambiguous", False)
                    resp_code = "AMBIGUOUS_SECTION_MATCH" if is_ambiguous else "SECTION_NOT_FOUND"
                    status_val = "clarification" if is_ambiguous else "engine_error"
                    return _build_response(
                        status=status_val,
                        raw_message=message,
                        disposition=disposition,
                        target_handler=target_handler,
                        response_code=resp_code,
                        response_text=conflict_res.get("error", "Could not resolve sections for conflict check."),
                        safe_to_route=True,
                        extracted_courses=extracted_courses,
                        engine_executed=False,
                        engine_result=conflict_res,
                    )

                # Real engine execution completed!
                s1 = conflict_res["section_1"]
                s2 = conflict_res["section_2"]

                # Check if timing information was uncertain / TBA / incomplete
                if conflict_res.get("is_uncertain"):
                    resp_code = "SCHEDULE_UNCERTAIN_TIMING"
                    resp_text = (
                        f"Cannot verify schedule conflict: {conflict_res.get('reason')} "
                        f"Without verified meeting times or confirmed asynchronous status, "
                        f"non-conflict cannot be guaranteed for {s1['course']} section {s1['section']} "
                        f"and {s2['course']} section {s2['section']}."
                    )
                    if unsupported_prefs:
                        resp_text += pref_note
                    return _build_response(
                        status="engine_executed",
                        raw_message=message,
                        disposition=disposition,
                        target_handler=target_handler,
                        response_code=resp_code,
                        response_text=resp_text,
                        actionable_guidance="Please consult the official course schedule or department for confirmed meeting times.",
                        safe_to_route=True,
                        extracted_courses=extracted_courses,
                        engine_executed=True,
                        engine_result=conflict_res,
                    )

                has_conflict = conflict_res.get("has_conflict", False)
                if has_conflict:
                    resp_code = "SCHEDULE_CONFLICT_FOUND"
                    resp_text = (
                        f"Schedule conflict detected: {s1['course']} section {s1['section']} and "
                        f"{s2['course']} section {s2['section']} overlap on {conflict_res.get('shared_days', '')} "
                        f"({s1['time']} vs {s2['time']})."
                    )
                else:
                    resp_code = "NO_SCHEDULE_CONFLICT"
                    if conflict_res.get("note"):
                        resp_text = (
                            f"No schedule conflict found: {s1['course']} section {s1['section']} and "
                            f"{s2['course']} section {s2['section']} do not conflict ({conflict_res.get('note')})."
                        )
                    else:
                        resp_text = (
                            f"No schedule conflict found: {s1['course']} section {s1['section']} ({s1['days']} {s1['time']}) "
                            f"and {s2['course']} section {s2['section']} ({s2['days']} {s2['time']}) do not overlap."
                        )

                if unsupported_prefs:
                    resp_text += pref_note

                return _build_response(
                    status="engine_executed",
                    raw_message=message,
                    disposition=disposition,
                    target_handler=target_handler,
                    response_code=resp_code,
                    response_text=resp_text,
                    safe_to_route=True,
                    extracted_courses=extracted_courses,
                    engine_executed=True,
                    engine_result=conflict_res,
                )

            # --- B2. Alternative Section Search ---
            if intent == ALTERNATIVE_SECTION:
                target_sec_input = req.target_section
                if not target_sec_input and req.sections:
                    target_sec_input = req.sections[0]
                if not target_sec_input and msg_pairs:
                    target_sec_input = msg_pairs[0]
                if not target_sec_input and msg_crns:
                    target_sec_input = msg_crns[0]

                # Check for contradictions between target_sec_input and message references
                if req.target_section:
                    t_row, t_err, _ = resolve_section(courses_catalog, req.target_section, req.term)
                    if not t_err:
                        t_crn = str(t_row["CRN"]).replace(".0", "")
                        t_code = normalize_course_code(t_row["COURSE"])
                        t_sect = str(t_row["SECT"]).strip().upper().lstrip("0")
                        if msg_crns and msg_crns[0] != t_crn:
                            return _build_response(
                                status="clarification",
                                raw_message=message,
                                disposition=disposition,
                                target_handler=target_handler,
                                response_code="CONTRADICTORY_SECTION_DETAILS",
                                response_text=(
                                    f"Contradictory section information detected: Message references CRN {msg_crns[0]}, "
                                    f"but target_section specifies CRN {t_crn}. Please clarify which section to replace."
                                ),
                                actionable_guidance="Resolve the mismatch between message CRN and target_section.",
                                safe_to_route=True,
                                missing_context=["consistent_target_section"],
                                extracted_courses=extracted_courses,
                                engine_executed=False,
                            )
                        if msg_pairs:
                            p = msg_pairs[0]
                            p_code = normalize_course_code(p["course"])
                            p_sect = str(p["section"]).strip().upper().lstrip("0")
                            if p_code != t_code or p_sect != t_sect:
                                return _build_response(
                                    status="clarification",
                                    raw_message=message,
                                    disposition=disposition,
                                    target_handler=target_handler,
                                    response_code="CONTRADICTORY_SECTION_DETAILS",
                                    response_text=(
                                        f"Contradictory section information detected: Message references {p['course']} section {p['section']}, "
                                        f"but target_section specifies {t_row['COURSE']} section {t_row['SECT']}. "
                                        f"Please clarify which section you wish to replace."
                                    ),
                                    actionable_guidance="Resolve the mismatch between message course/section and target_section.",
                                    safe_to_route=True,
                                    missing_context=["consistent_target_section"],
                                    extracted_courses=extracted_courses,
                                    engine_executed=False,
                                )

                if not target_sec_input and extracted_courses:
                    course_name = extracted_courses[0]
                    return _build_response(
                        status="clarification",
                        raw_message=message,
                        disposition=disposition,
                        target_handler=target_handler,
                        response_code="MISSING_TARGET_SECTION",
                        response_text=(
                            f"To find alternatives for {course_name}, please specify the current section number or CRN "
                            f"you wish to replace (e.g. 'Is there another section for {course_name} section 001?')."
                        ),
                        actionable_guidance="Specify the section number or CRN of the course to be replaced.",
                        safe_to_route=True,
                        missing_context=["target_section"],
                        extracted_courses=extracted_courses,
                        engine_executed=False,
                    )

                if not target_sec_input:
                    return _build_response(
                        status="clarification",
                        raw_message=message,
                        disposition=disposition,
                        target_handler=target_handler,
                        response_code="MISSING_TARGET_SECTION",
                        response_text="Please specify the course and section number or CRN you want to find alternatives for.",
                        actionable_guidance="Provide the target course and section to replace.",
                        safe_to_route=True,
                        missing_context=["target_section"],
                        extracted_courses=extracted_courses,
                        engine_executed=False,
                    )

                # Selected schedule handling: distinguish None (omitted) from [] (explicitly empty schedule)
                if req.selected_sections is None:
                    return _build_response(
                        status="clarification",
                        raw_message=message,
                        disposition=disposition,
                        target_handler=target_handler,
                        response_code="MISSING_SCHEDULE_CONTEXT",
                        response_text=(
                            "To find non-conflicting alternative sections, please provide your current schedule or "
                            "enrolled section CRNs in selected_sections (or provide an empty list if you have no other enrolled classes)."
                        ),
                        actionable_guidance="Provide enrolled section CRNs in selected_sections context, or supply [] for an empty schedule.",
                        safe_to_route=True,
                        missing_context=["selected_sections"],
                        extracted_courses=extracted_courses,
                        engine_executed=False,
                    )

                try:
                    alt_res = evaluate_alternative_sections(
                        courses=courses_catalog,
                        target_section_input=target_sec_input,
                        selected_sections_input=req.selected_sections,
                        term=req.term,
                        max_results=3,
                    )
                except Exception as exc:
                    logger.error(
                        "Alternative section search failed with exception type %s.",
                        type(exc).__name__,
                    )
                    return _build_response(
                        status="engine_error",
                        raw_message=message,
                        disposition=disposition,
                        target_handler=target_handler,
                        response_code="ENGINE_EXECUTION_ERROR",
                        response_text="An internal error occurred while searching for alternative sections.",
                        safe_to_route=True,
                        extracted_courses=extracted_courses,
                        engine_executed=False,
                        engine_result={"error": "Internal alternative section search error"},
                    )

                if not alt_res.get("success"):
                    if alt_res.get("is_engine_error"):
                        resp_code = "ENGINE_EXECUTION_ERROR"
                        status_val = "engine_error"
                    elif alt_res.get("is_ambiguous"):
                        resp_code = "AMBIGUOUS_SECTION_MATCH"
                        status_val = "clarification"
                    else:
                        resp_code = "SECTION_NOT_FOUND"
                        status_val = "engine_error"
                    return _build_response(
                        status=status_val,
                        raw_message=message,
                        disposition=disposition,
                        target_handler=target_handler,
                        response_code=resp_code,
                        response_text=alt_res.get("error", "Could not evaluate alternative sections."),
                        safe_to_route=True,
                        extracted_courses=extracted_courses,
                        engine_executed=False,
                        engine_result=alt_res,
                    )

                # Real engine execution completed!
                alt_count = alt_res.get("count", 0)
                target_rec = alt_res.get("target_section", {})
                course_label = target_rec.get("course", "course")
                sec_label = target_rec.get("section", "")
                limits = alt_res.get("limitations", [])

                if alt_count > 0:
                    resp_code = "ALTERNATIVE_SECTIONS_FOUND"
                    alt_summaries = []
                    for a in alt_res.get("alternatives", []):
                        note_suffix = f", {a['schedule_note']}" if not a.get("timing_verified", True) else ""
                        alt_summaries.append(
                            f"Section {a['section']} (CRN {a['crn']}, {a['days']} {a['time']}, {a['seats_remaining']} seats open{note_suffix})"
                        )
                    alt_text = "; ".join(alt_summaries)
                    resp_text = (
                        f"Found {alt_count} non-conflicting alternative section(s) for {course_label} "
                        f"(replacing Section {sec_label}): {alt_text}."
                    )
                else:
                    resp_code = "NO_ALTERNATIVE_SECTIONS_FOUND"
                    resp_text = (
                        f"No non-conflicting alternative sections with open seats were found for {course_label} "
                        f"in the course catalog."
                    )

                if limits:
                    resp_text += f" Limitation: {'; '.join(limits)}"
                if unsupported_prefs:
                    resp_text += pref_note

                return _build_response(
                    status="engine_executed",
                    raw_message=message,
                    disposition=disposition,
                    target_handler=target_handler,
                    response_code=resp_code,
                    response_text=resp_text,
                    safe_to_route=True,
                    extracted_courses=extracted_courses,
                    engine_executed=True,
                    engine_result=alt_res,
                )

        # C. Online Override Screening - Directed to UI
        if target_handler == HANDLER_OVERRIDE:
            return _build_response(
                status="engine_unavailable",
                raw_message=message,
                disposition=disposition,
                target_handler=target_handler,
                response_code="OVERRIDE_DIRECTED_TO_UI",
                response_text=(
                    "Online course override screening is available in the Online Course Override Evaluator "
                    "form below. Please provide your circumstance and documentation status there."
                ),
                actionable_guidance="Fill in the Online Course Override Evaluator form below.",
                safe_to_route=True,
                extracted_courses=extracted_courses,
                engine_executed=False,
            )

    # Fallback
    return _build_response(
        status="unsupported",
        raw_message=message,
        disposition=disposition or "unsupported",
        target_handler=target_handler or "none",
        response_code=response_code,
        response_text=response_text or "Unable to process query.",
        safe_to_route=False,
        engine_executed=False,
    )


@router.post("/conversation", response_model=ConversationResponse)
async def handle_conversation(req: ConversationRequest, request: Request):
    """Run synchronous engines off-loop and prevent late publication on disconnect."""
    cancellation = threading.Event()
    worker = asyncio.create_task(asyncio.to_thread(_handle_conversation_sync, req, cancellation))
    while True:
        done, _ = await asyncio.wait({worker}, timeout=0.05)
        if worker in done:
            return worker.result()
        if await request.is_disconnected():
            cancellation.set()
            # The active source request still ends under its configured network
            # timeout. Awaiting it here leaves no detached task that could publish
            # after the client has abandoned the request.
            await worker
            raise HTTPException(status_code=499, detail="Client disconnected before acquisition completed.")
