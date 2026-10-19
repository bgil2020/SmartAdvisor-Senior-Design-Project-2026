import logging
import re
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
    resolve_section,
    normalize_course_code,
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
                    return ConversationResponse(
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
                    return ConversationResponse(
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
                                return ConversationResponse(
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
                                        return ConversationResponse(
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
                                    return ConversationResponse(
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
                    return ConversationResponse(
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
                            return ConversationResponse(
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
                                return ConversationResponse(
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
