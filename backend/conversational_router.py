"""FastAPI router for deterministic conversational assistant handoff."""
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

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

from .compatibility_engine import evaluate_compatibility

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

        # B. Scheduling Engine (conflict / alternative) - Directed to UI
        if target_handler == HANDLER_SCHEDULING:
            return ConversationResponse(
                status="engine_unavailable",
                raw_message=message,
                disposition=disposition,
                target_handler=target_handler,
                response_code="SCHEDULING_DIRECTED_TO_UI",
                response_text=(
                    "Schedule conflict and section alternative questions are currently handled via "
                    "the Course Catalog and Schedule Calendar above. Please view sections or select "
                    "'Find Alternatives' on an enrolled section."
                ),
                actionable_guidance="Use the Course Catalog and Section search controls above.",
                safe_to_route=True,
                extracted_courses=extracted_courses,
                engine_executed=False,
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
