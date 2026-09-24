# Conversational Response Policy

## Purpose and Current Limitations
The `response_policy.py` module defines the rules for how the SmartAdvisor conversational layer routes requests, asks for clarification, handles unsupported queries, and escalates to human advisors. 

**Current Limitations:**
- This module relies entirely on standard-library keyword matching and rules. It does not use any AI/LLM for generation or routing.
- Responses are fully deterministic and bound by predefined text strings. 

## Input Dependency
The policy strictly consumes the output of the `extract_entities()` function from `entity_extractor.py`. It uses the extracted intents, validation flags, missing fields, and entities to formulate the final conversational response without modifying the extraction logic itself.

## Output Schema
The core function `build_conversation_response(message: str) -> dict` returns a JSON-serializable dictionary with exactly these top-level keys:

- `raw_message`: The original student message.
- `disposition`: Action category (`route_core_engine`, `clarify`, `future_rag_candidate`, `advisor_escalation`, `unsupported`).
- `target_handler`: Destination engine (`course_compatibility_engine`, `scheduling_engine`, `online_override_eligibility_engine`, `future_informational_rag`, `academic_advisor`, `none`).
- `intent`: The inherited intent from the classifier.
- `entities`: The completely unmodified result dict from `extract_entities()`.
- `needs_clarification`: Boolean indicating if the prompt lacked required details.
- `missing_fields`: List of fields identified as missing.
- `validation_errors`: Any extraction validation errors (e.g., conflicting modalities).
- `response_code`: A standardized string code (e.g., `CORE_REQUEST_READY`, `AMBIGUOUS_REQUEST`).
- `response_text`: Deterministic, concise, student-facing plain text response.
- `safe_to_route`: Boolean indicating if the request can be safely sent to the backend.
- `future_rag_candidate`: Boolean indicating if this is an informational query for a future RAG system.
- `reason`: Internal/status reasoning.

## Core-Engine Mapping
When requests are complete and valid, they are mapped to one of the three core deterministic backend engines:
- `course_compatibility_check` -> `course_compatibility_engine`
- `schedule_conflict_check` or `alternative_section_search` -> `scheduling_engine`
- `online_override_screening` -> `online_override_eligibility_engine`

## Clarification and Validation Behavior
If the extractor flags validation errors (e.g., conflicting preferences), or identifies missing fields, the policy sets `disposition` to `clarify` and prevents routing to backend engines (`safe_to_route = False`). It prompts the student to provide the specific missing context (like a second course code or section details) or choose a single goal.

## Advisor-Escalation Boundary
The policy contains a conservative guardrail (`requires_advisor_escalation`) to detect explicit requests for official academic action or guarantees. Requests like "approve my override", "register me", or "will I graduate on time" are intercepted and escalate to `academic_advisor`. The system explicitly informs the student that an advisor or official university office must handle the request.

## Future Informational RAG Candidate Boundary
We have established a bounded future informational RAG route. Informational questions about course prerequisites, topics covered, catalog descriptions, and policy contents are flagged as a `future_rag_candidate`. 
**Explicit Statement:** Actual RAG/LLM retrieval is **not** implemented yet. When a candidate is detected, the system safely explains that source-grounded informational lookup is not enabled in the prototype.

**Test Alignment Note:** Informational/RAG questions are currently represented solely as a response-policy `disposition`, not as a new classifier intent. The intent classifier and entity extractor maintain regression tests ensuring these informational prompts are not accidentally misrouted to deterministic decision engines. Actual RAG/LLM retrieval is not implemented or enabled.
- A general informational question such as "What does the online override policy say?" may initially inherit an `online_override_screening` classifier intent because of keyword matching.
- The response policy checks informational policy wording before core-engine routing and assigns `future_rag_candidate`.
- A personal question such as "Am I eligible for an online override?" remains eligible for the deterministic override-screening route when otherwise complete.
- An official request such as "Can you approve my override?" remains advisor escalation.

## Integration Note
This module is temporary conversation-layer routing policy. It acts as an interim component until shared FastAPI/backend contracts, data models, and actual integrated API endpoints are available.

## Examples

### 1. Core-Ready Response
**Input:** "Can I take COP 3330 and CEN 4010 together?"
```json
{
  "raw_message": "Can I take COP 3330 and CEN 4010 together?",
  "disposition": "route_core_engine",
  "target_handler": "course_compatibility_engine",
  "response_code": "CORE_REQUEST_READY",
  "response_text": "Your request is ready to be checked for course compatibility.",
  "safe_to_route": true,
  "future_rag_candidate": false,
  ...
}
```

### 2. Clarification Response (Ambiguous Workload)
**Input:** "Is COP 3330 risky?"
```json
{
  "raw_message": "Is COP 3330 risky?",
  "disposition": "clarify",
  "target_handler": "none",
  "response_code": "AMBIGUOUS_REQUEST",
  "response_text": "Are you asking about the general difficulty/workload of this course, or whether it is compatible with another course? If comparing, please provide the other course code.",
  "safe_to_route": false,
  ...
}
```

### 3. Future RAG Candidate Response
**Input:** "What topics are covered in COP 3530?"
```json
{
  "raw_message": "What topics are covered in COP 3530?",
  "disposition": "future_rag_candidate",
  "target_handler": "future_informational_rag",
  "response_code": "FUTURE_RAG_NOT_AVAILABLE",
  "response_text": "Source-grounded informational lookup is not enabled in the current prototype. Please check the official catalog or speak with an advisor.",
  "safe_to_route": false,
  "future_rag_candidate": true,
  ...
}
```

### 4. Advisor Escalation Response
**Input:** "Can you register me for COP 3530?"
```json
{
  "raw_message": "Can you register me for COP 3530?",
  "disposition": "advisor_escalation",
  "target_handler": "academic_advisor",
  "response_code": "ADVISOR_ESCALATION_REQUIRED",
  "response_text": "An academic advisor or authorized university office must make the official decision or action regarding your request.",
  "safe_to_route": false,
  ...
}
```
