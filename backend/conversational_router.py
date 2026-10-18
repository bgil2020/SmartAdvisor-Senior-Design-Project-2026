import logging
from typing import Any, Literal
from fastapi import APIRouter, HTTPException
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
    )
    from backend.app.conversational.intent_classifier import (
        SCHEDULE_CONFLICT,
        ALTERNATIVE_SECTION,
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
    )
    from app.conversational.intent_classifier import (
        SCHEDULE_CONFLICT,
        ALTERNATIVE_SECTION,
    )

from .compatibility_engine import evaluate_compatibility
from .scheduling_service import (
    get_course_catalog,
    evaluate_schedule_conflict,
    evaluate_alternative_sections,
)

router = APIRouter(tags=["Conversational Assistant"])


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
    term: int | str | None = Field(default=None, description="Term code for section lookups, e.g. 202608")
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
    disclaimer: str = (
        "SmartAdvisor conversational layer is a rule-based decision-support prototype. "
        "It does not approve overrides or register courses."
    )


@router.post("/conversation", response_model=ConversationResponse)
def handle_conversation(req: ConversationRequest):
    """
    Evaluates student prompt using deterministic intent classifier and response policy.
    When intent is course compatibility and full student/workload context is supplied,
    executes the authoritative compatibility engine directly.
    """
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    policy_resp = build_conversation_response(message)
    disposition = policy_resp.get("disposition")
    target_handler = policy_resp.get("target_handler")
    response_code = policy_resp.get("response_code", "UNKNOWN")
    response_text = policy_resp.get("response_text", "")
    entities = policy_resp.get("entities", {})
    extracted_courses = entities.get("course_codes", [])

    # 1. Escalation to advisor
    if disposition == DISPOSITION_ESCALATION:
        return ConversationResponse(
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

    # 2. Informational RAG queries (Inactive prototype candidate)
    if disposition == DISPOSITION_RAG:
        return ConversationResponse(
            status="rag_inactive",
            raw_message=message,
            disposition=disposition,
            target_handler=target_handler,
            response_code=response_code,
            response_text=response_text,
            actionable_guidance="Informational RAG retrieval is planned for a future milestone and is not active in this prototype.",
            safe_to_route=False,
            engine_executed=False,
            extracted_courses=extracted_courses,
        )

    # 3. Clarification requested by response policy
    if disposition == DISPOSITION_CLARIFY:
        return ConversationResponse(
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
        return ConversationResponse(
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
                return ConversationResponse(
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
                return ConversationResponse(
                    status="engine_error",
                    raw_message=message,
                    disposition=disposition,
                    target_handler=target_handler,
                    response_code="ENGINE_EXECUTION_ERROR",
                    response_text=f"Compatibility engine encountered an error: {exc}",
                    safe_to_route=True,
                    extracted_courses=extracted_courses,
                    engine_executed=True,
                    engine_result={"error": str(exc)},
                )

            if not engine_output.get("success"):
                return ConversationResponse(
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
            return ConversationResponse(
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

            # --- B1. Schedule Conflict Check ---
            if intent == SCHEDULE_CONFLICT:
                sec1_input = None
                sec2_input = None

                # 1. Check explicit structured sections in request
                if req.sections and len(req.sections) >= 2:
                    sec1_input = req.sections[0]
                    sec2_input = req.sections[1]
                # 2. Check bound course-section pairs extracted from message
                elif len(entities.get("course_section_pairs", [])) >= 2:
                    pairs = entities["course_section_pairs"]
                    sec1_input = pairs[0]
                    sec2_input = pairs[1]
                # 3. Check CRNs extracted from message
                elif len(entities.get("crns", [])) >= 2:
                    crns = entities["crns"]
                    sec1_input = crns[0]
                    sec2_input = crns[1]

                # Check if sections are missing
                if not sec1_input or not sec2_input:
                    missing_parts = []
                    if len(extracted_courses) < 2 and len(entities.get("crns", [])) < 2:
                        missing_parts.append("two courses")
                    if not entities.get("course_section_pairs") and not entities.get("crns"):
                        missing_parts.append("specific section numbers or CRNs")

                    detail_msg = f" ({', '.join(missing_parts)})" if missing_parts else ""
                    return ConversationResponse(
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
                    logger.exception("Conflict evaluation encountered an unexpected error: %s", exc)
                    return ConversationResponse(
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
                    return ConversationResponse(
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
                has_conflict = conflict_res.get("has_conflict", False)
                s1 = conflict_res["section_1"]
                s2 = conflict_res["section_2"]
                if has_conflict:
                    resp_code = "SCHEDULE_CONFLICT_FOUND"
                    resp_text = (
                        f"Schedule conflict detected: {s1['course']} section {s1['section']} and "
                        f"{s2['course']} section {s2['section']} overlap on {conflict_res.get('shared_days', '')} "
                        f"({s1['time']} vs {s2['time']})."
                    )
                else:
                    resp_code = "NO_SCHEDULE_CONFLICT"
                    resp_text = (
                        f"No schedule conflict found: {s1['course']} section {s1['section']} ({s1['days']} {s1['time']}) "
                        f"and {s2['course']} section {s2['section']} ({s2['days']} {s2['time']}) do not overlap."
                    )

                return ConversationResponse(
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
                if not target_sec_input and entities.get("course_section_pairs"):
                    target_sec_input = entities["course_section_pairs"][0]
                if not target_sec_input and entities.get("crns"):
                    target_sec_input = entities["crns"][0]

                if not target_sec_input and extracted_courses:
                    course_name = extracted_courses[0]
                    return ConversationResponse(
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
                    return ConversationResponse(
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
                    return ConversationResponse(
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
                    logger.exception("Alternative section search encountered an unexpected error: %s", exc)
                    return ConversationResponse(
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
                    return ConversationResponse(
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

                if alt_count > 0:
                    resp_code = "ALTERNATIVE_SECTIONS_FOUND"
                    alt_summaries = []
                    for a in alt_res.get("alternatives", []):
                        alt_summaries.append(
                            f"Section {a['section']} (CRN {a['crn']}, {a['days']} {a['time']}, {a['seats_remaining']} seats open)"
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

                return ConversationResponse(
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
            return ConversationResponse(
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
    return ConversationResponse(
        status="unsupported",
        raw_message=message,
        disposition=disposition or "unsupported",
        target_handler=target_handler or "none",
        response_code=response_code,
        response_text=response_text or "Unable to process query.",
        safe_to_route=False,
        engine_executed=False,
    )
