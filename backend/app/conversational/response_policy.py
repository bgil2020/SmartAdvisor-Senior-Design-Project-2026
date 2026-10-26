import re
from typing import Dict, Any
try:
    from backend.app.conversational.entity_extractor import extract_entities
    from backend.app.conversational.intent_classifier import (
        COURSE_COMPATIBILITY,
        SCHEDULE_CONFLICT,
        ALTERNATIVE_SECTION,
        ONLINE_OVERRIDE,
        CLARIFICATION,
        UNSUPPORTED_SCOPE
    )
    from backend.app.conversational.parser_contract import (
        INTENT_COURSE_COMPATIBILITY,
        INTENT_SCHEDULE_CONFLICT,
        INTENT_ALTERNATIVE_SECTION,
        INTENT_ONLINE_OVERRIDE,
        INTENT_ADVISOR_ESCALATION,
        INTENT_INFORMATIONAL_RAG,
        INTENT_CLARIFICATION,
        INTENT_UNSUPPORTED,
    )
except ImportError:
    from app.conversational.entity_extractor import extract_entities
    from app.conversational.intent_classifier import (
        COURSE_COMPATIBILITY,
        SCHEDULE_CONFLICT,
        ALTERNATIVE_SECTION,
        ONLINE_OVERRIDE,
        CLARIFICATION,
        UNSUPPORTED_SCOPE
    )
    from app.conversational.parser_contract import (
        INTENT_COURSE_COMPATIBILITY,
        INTENT_SCHEDULE_CONFLICT,
        INTENT_ALTERNATIVE_SECTION,
        INTENT_ONLINE_OVERRIDE,
        INTENT_ADVISOR_ESCALATION,
        INTENT_INFORMATIONAL_RAG,
        INTENT_CLARIFICATION,
        INTENT_UNSUPPORTED,
    )

# Constants for Disposition
DISPOSITION_ROUTE_CORE = "route_core_engine"
DISPOSITION_CLARIFY = "clarify"
DISPOSITION_RAG = "future_rag_candidate"
DISPOSITION_ESCALATION = "advisor_escalation"
DISPOSITION_UNSUPPORTED = "unsupported"

# Constants for Target Handlers
HANDLER_COMPATIBILITY = "course_compatibility_engine"
HANDLER_SCHEDULING = "scheduling_engine"
HANDLER_OVERRIDE = "online_override_eligibility_engine"
HANDLER_RAG = "future_informational_rag"
HANDLER_ADVISOR = "academic_advisor"
HANDLER_NONE = "none"

# Constants for Response Codes
CODE_CORE_READY = "CORE_REQUEST_READY"
CODE_MISSING_COURSE_CODES = "MISSING_COURSE_CODES"
CODE_MISSING_SECOND_COURSE = "MISSING_SECOND_COURSE"
CODE_MISSING_SCHEDULE_DETAILS = "MISSING_SCHEDULE_DETAILS"
CODE_AMBIGUOUS_REQUEST = "AMBIGUOUS_REQUEST"
CODE_UNSUPPORTED_REQUEST = "UNSUPPORTED_REQUEST"
CODE_FUTURE_RAG = "FUTURE_RAG_NOT_AVAILABLE"
CODE_ADVISOR_ESCALATION = "ADVISOR_ESCALATION_REQUIRED"
CODE_INVALID_DETAILS = "INVALID_OR_CONFLICTING_DETAILS"

def requires_advisor_escalation(message: str) -> bool:
    msg = message.lower()
    if re.search(r'\b(approve|grant|give)\b.*\boverride\b', msg):
        return True
    if re.search(r'\bregister\b', msg) or re.search(r'\benroll\b', msg):
        return True
    if re.search(r'\bgraduate on time\b', msg) or re.search(r'\bguarantee\b.*\bgraduat', msg):
        return True
    if re.search(r'\b(waiver|exception)\b', msg) and re.search(r'\b(approve|grant|official)\b', msg):
        return True
    return False

def is_future_rag_candidate(message: str, extractor_result: dict) -> bool:
    msg = message.lower()
    if re.search(r'\btopics?\b.*\bcovered\b', msg):
        return True
    if re.search(r'\bprerequisites?\b', msg):
        return True
    if re.search(r'\bpolicy\b.*\bsay\b', msg):
        return True
    if re.search(r'\bcatalog description\b', msg):
        return True
    return False

def is_ambiguous_single_course_workload(message: str, entities: dict) -> bool:
    intent = entities.get("intent")
    if intent not in (COURSE_COMPATIBILITY, INTENT_COURSE_COMPATIBILITY):
        return False
    if len(entities.get("course_codes", [])) != 1:
        return False
    msg_lower = message.lower()
    if re.search(r'\b(with|together|and)\b', msg_lower):
        return False
    if re.search(r'\b(risky|hard|difficult|workload|time-consuming|manageable)\b', msg_lower):
        return True
    return False

def build_conversation_response(message: str, parsed_result: Any = None) -> dict:
    if parsed_result is not None:
        if hasattr(parsed_result, "to_extractor_dict"):
            entities = parsed_result.to_extractor_dict()
        elif isinstance(parsed_result, dict):
            entities = parsed_result
        else:
            entities = extract_entities(message)
    else:
        entities = extract_entities(message)

    intent = entities.get("intent")
    validation_errors = entities.get("validation_errors", [])
    needs_clarification = entities.get("needs_clarification", False)
    missing_fields = entities.get("missing_fields", [])

    parser_source = entities.get("parser_source", "deterministic")
    fallback_used = entities.get("fallback_used", False)
    fallback_reason = entities.get("fallback_reason")
    model_id = entities.get("model_id")

    base_meta = {
        "parser_source": parser_source,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "model_id": model_id,
    }

    # 1. Advisor escalation (Deterministic safety gate + LLM interpretation)
    if requires_advisor_escalation(message) or intent in (INTENT_ADVISOR_ESCALATION, "advisor_escalation"):
        return {
            "raw_message": message,
            "disposition": DISPOSITION_ESCALATION,
            "target_handler": HANDLER_ADVISOR,
            "intent": intent,
            "entities": entities,
            "needs_clarification": False,
            "missing_fields": missing_fields,
            "validation_errors": validation_errors,
            "response_code": CODE_ADVISOR_ESCALATION,
            "response_text": "An academic advisor or authorized university office must make the official decision or action regarding your request.",
            "safe_to_route": False,
            "future_rag_candidate": False,
            "reason": "Request requires official advisor action."
        }

    # 2. Conflicting/invalid extracted details
    if validation_errors:
        return {
            "raw_message": message,
            "disposition": DISPOSITION_CLARIFY,
            "target_handler": HANDLER_NONE,
            "intent": intent,
            "entities": entities,
            "needs_clarification": True,
            "missing_fields": missing_fields,
            "validation_errors": validation_errors,
            "response_code": CODE_INVALID_DETAILS,
            "response_text": "Please provide one clear version of the conflicting information.",
            "safe_to_route": False,
            "future_rag_candidate": False,
            "reason": "Conflicting or invalid details detected."
        }

    # 3. Future informational RAG candidate
    if is_future_rag_candidate(message, entities) or intent in (INTENT_INFORMATIONAL_RAG, "future_rag_candidate"):
        return {
            "raw_message": message,
            "disposition": DISPOSITION_RAG,
            "target_handler": HANDLER_RAG,
            "intent": intent,
            "entities": entities,
            "needs_clarification": False,
            "missing_fields": missing_fields,
            "validation_errors": validation_errors,
            "response_code": CODE_FUTURE_RAG,
            "response_text": "Source-grounded informational lookup is not enabled in the current prototype. Please check the official catalog or speak with an advisor.",
            "safe_to_route": False,
            "future_rag_candidate": True,
            "reason": "Informational question identified for future RAG implementation."
        }

    # 4. Clarification/missing required data
    if needs_clarification or missing_fields or intent in (CLARIFICATION, INTENT_CLARIFICATION):
        code = CODE_AMBIGUOUS_REQUEST
        text = "Please choose one goal: compare course workload, check schedule/sections, or screen an online override."
        reason = "Missing required details or ambiguous intent."

        if is_ambiguous_single_course_workload(message, entities):
            code = CODE_AMBIGUOUS_REQUEST
            text = "Are you asking about the general difficulty/workload of this course, or whether it is compatible with another course? If comparing, please provide the other course code."
            reason = "Ambiguous single-course workload/compatibility question."
        elif intent in (COURSE_COMPATIBILITY, INTENT_COURSE_COMPATIBILITY) and len(entities.get("course_codes", [])) == 1:
            code = CODE_MISSING_SECOND_COURSE
            text = "Please provide the other course code you'd like to compare."
        elif "course_codes" in missing_fields or (intent in [COURSE_COMPATIBILITY, INTENT_COURSE_COMPATIBILITY, SCHEDULE_CONFLICT, INTENT_SCHEDULE_CONFLICT, ALTERNATIVE_SECTION, INTENT_ALTERNATIVE_SECTION, ONLINE_OVERRIDE, INTENT_ONLINE_OVERRIDE] and len(entities.get("course_codes", [])) == 0 and len(entities.get("crns", [])) == 0):
            code = CODE_MISSING_COURSE_CODES
            text = "Please provide the course code(s), for example 'COP 3530'."
        elif "section_identifiers" in missing_fields or "schedule_constraints" in missing_fields:
            code = CODE_MISSING_SCHEDULE_DETAILS
            text = "Please provide the specific missing section, days, or meeting time."

        return {
            "raw_message": message,
            "disposition": DISPOSITION_CLARIFY,
            "target_handler": HANDLER_NONE,
            "intent": intent,
            "entities": entities,
            "needs_clarification": True,
            "missing_fields": missing_fields,
            "validation_errors": validation_errors,
            "response_code": code,
            "response_text": text,
            "safe_to_route": False,
            "future_rag_candidate": False,
            "reason": reason
        }

    # 5. Ready core deterministic routing
    if intent in (COURSE_COMPATIBILITY, INTENT_COURSE_COMPATIBILITY):
        return {
            "raw_message": message,
            "disposition": DISPOSITION_ROUTE_CORE,
            "target_handler": HANDLER_COMPATIBILITY,
            "intent": intent,
            "entities": entities,
            "needs_clarification": False,
            "missing_fields": missing_fields,
            "validation_errors": validation_errors,
            "response_code": CODE_CORE_READY,
            "response_text": "Your request is ready to be checked for course compatibility.",
            "safe_to_route": True,
            "future_rag_candidate": False,
            "reason": "All required data for compatibility check is present."
        }

    elif intent in (SCHEDULE_CONFLICT, INTENT_SCHEDULE_CONFLICT, ALTERNATIVE_SECTION, INTENT_ALTERNATIVE_SECTION):
        return {
            "raw_message": message,
            "disposition": DISPOSITION_ROUTE_CORE,
            "target_handler": HANDLER_SCHEDULING,
            "intent": intent,
            "entities": entities,
            "needs_clarification": False,
            "missing_fields": missing_fields,
            "validation_errors": validation_errors,
            "response_code": CODE_CORE_READY,
            "response_text": "Your request is ready to be checked by the scheduling engine.",
            "safe_to_route": True,
            "future_rag_candidate": False,
            "reason": "All required data for scheduling check is present."
        }

    elif intent in (ONLINE_OVERRIDE, INTENT_ONLINE_OVERRIDE):
        return {
            "raw_message": message,
            "disposition": DISPOSITION_ROUTE_CORE,
            "target_handler": HANDLER_OVERRIDE,
            "intent": intent,
            "entities": entities,
            "needs_clarification": False,
            "missing_fields": missing_fields,
            "validation_errors": validation_errors,
            "response_code": CODE_CORE_READY,
            "response_text": "Your request is ready for online override screening.",
            "safe_to_route": True,
            "future_rag_candidate": False,
            "reason": "All required data for override screening is present."
        }

    # 6. Unsupported scope
    return {
        "raw_message": message,
        "disposition": DISPOSITION_UNSUPPORTED,
        "target_handler": HANDLER_NONE,
        "intent": intent,
        "entities": entities,
        "needs_clarification": False,
        "missing_fields": missing_fields,
        "validation_errors": validation_errors,
        "response_code": CODE_UNSUPPORTED_REQUEST,
        "response_text": "This prototype can currently help with course compatibility, schedule/section questions, and online-override screening.",
        "safe_to_route": False,
        "future_rag_candidate": False,
        "reason": "Request scope is unsupported."
    }
