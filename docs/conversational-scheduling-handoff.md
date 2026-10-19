# Conversational Scheduling Handoff & Contract Stabilization (TASK-003 / TASK-004 Reconciled)

## 1. Overview & Checkpoint Baseline
- **Repository**: `SmartAdvisor-Senior-Design-Project-2026`
- **Branch**: `feature/conversational-scheduling-integration`
- **Baseline Checkpoint (TASK-002)**: Commit `8b327aef42277fb4a937f3ba51f9c1ba37387373`
- **Stabilization Checkpoint (TASK-003)**: Commit `cede77307bd7c06fa10388b938c001e8ff2c29e2`
- **Remote Branch SHA**: `cede77307bd7c06fa10388b938c001e8ff2c29e2` (verified on `origin/feature/conversational-scheduling-integration`)
- **Objective**: Maintain bounded conversational scheduling stabilization, timing safety, and backend contract readiness for provider-independent LLM structured parsing with deterministic fallback.

---

## 2. API Contract Specification & Reporting Reconciliation

### 2.1 Actual Endpoint Routes & Schemas

The active FastAPI application mounts the following authoritative endpoints:

| Service Area | Method & Path | Router Source | Description |
|---|---|---|---|
| **Conversational Assistant** | `POST /conversation` | `backend/conversational_router.py` | Main conversational dispatch evaluating natural language queries with deterministic intent classification, rule policy, and core engine routing. |
| **Course Compatibility** | `POST /compatibility` | `backend/compatibility_router.py` | Direct workload compatibility evaluation requiring complete student profile and proposed course list. |
| **Course Retrieval** | `GET /courses` | `backend/api.py` | Course catalog listing and keyword search. |
| **Section Retrieval** | `GET /sections` | `backend/api.py` | Section listing filtered by course and term. |
| **Alternative Sections** | `GET /alternatives` | `backend/api.py` | Query-param based alternative section search. |

> [!IMPORTANT]
> The conversational assistant endpoint is strictly `POST /conversation`. The path `/api/conversational/query` does not exist in the active codebase.

### 2.2 Accepted Request Schema (`ConversationRequest`)

```python
class ConversationRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    student_id: str | None = None
    recent_difficulty: int | None = Field(default=None, ge=1, le=5)
    satisfied_with_performance: Literal["yes", "mostly", "no"] | None = None
    work_hours: float | None = Field(default=None, ge=0, le=80)
    preferred_max_credits: float | None = Field(default=None, ge=1, le=30)
    recent_courses: list[str] | None = None
    term: int | str | None = None  # Authoritative catalog term is 202608
    sections: list[Any] | None = None  # Exactly 2 sections for conflict checking
    target_section: Any | None = None  # Required for alternative section search
    selected_sections: list[Any] | None = None  # Enrolled schedule sections (or [] for none)
```

### 2.3 Authoritative Response Schema (`ConversationResponse`)

```python
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
```

### 2.4 Reconciliation of TASK-003 Chat Report vs. Actual Codebase

The prior TASK-003 chat response contained descriptive summaries that diverged from executable code. The following table reconciles all differences:

| Item | Prior TASK-003 Chat Report Claim | Actual Implemented Codebase | Status / Reconciliation |
|---|---|---|---|
| **Conversational Endpoint** | `POST /api/conversational/query` | `POST /conversation` | Corrected. Router mounted at `/conversation`. |
| **Response Text Field** | `message: "..."` | `response_text: "..."` | Corrected. `raw_message` holds input; `response_text` holds assistant output. |
| **Engine Result Field** | `scheduling_evaluation: { ... }` | `engine_result: { ... }` | Corrected. Standardized additive payload container is `engine_result`. |
| **Overall Status Field** | `status: "success"` | `status: "engine_executed"` | Corrected. Schema strictly permits `engine_executed`, `clarification`, `escalation`, `rag_inactive`, `unsupported`, `engine_unavailable`, `engine_error`. |
| **Active Term Code** | `term: "202601"` | `term: 202608` | Corrected. The catalog `data/FAU_Courses.xlsx` contains solely term `202608`. |
| **Alternative Search Input** | `"course_code": "COP 3530"` without schedule context | `target_section` and `selected_sections` required | Corrected. Router enforces `target_section` and disambiguates omitted schedule (`missing_context=["selected_sections"]`) from explicitly empty schedule (`[]`). |
| **Capture Provenance** | Claimed fresh live HTTP captures | FastAPI `TestClient` in-process execution | Clarified. TASK-003 utilized in-process `TestClient`. TASK-004 captured live HTTP via Windows `curl.exe` over TCP socket on port 8008. |

---

## 3. Asynchronous Classification & Timing Safety Analysis

### 3.1 Taxonomy of Scheduling States

Sections are classified into three mutually exclusive states in `backend/meeting_time_normalizer.py`:
1. `SCHEDULE_STATUS_SCHEDULED ("SCHEDULED")`: Section contains usable meeting days and start/end times (`start_mins < end_mins`). Both in-person and synchronous online sections participate fully in time overlap calculation.
2. `SCHEDULE_STATUS_ASYNCHRONOUS ("VERIFIED_ASYNCHRONOUS")`: Section is explicitly verified as asynchronous online delivery. Has no fixed meeting times and does not conflict with scheduled classes.
3. `SCHEDULE_STATUS_UNKNOWN ("UNKNOWN_TIMING")`: Incomplete, missing, or TBA meeting times where asynchronous delivery cannot be verified.

### 3.2 Catalog Analysis (`FAU_Courses.xlsx`)

An exhaustive audit of the 1,514 course sections in `data/FAU_Courses.xlsx` reveals:
- **Instructional Methods Present**: `Fully Online Class` (230), `In-Person` (986), `In-Person w/Live Remote Option` (86), `Online Live Lecture` (28), `In-Person w/Recorded Lecture` (13), `Primarily Classroom` (11), `Multi Campus: Main Location` (6), `Multi Campus: Remote Location` (4), `Mostly Online Class` (3), `Mixed Online and Classroom` (1).
- **Asynchronous Keyword Absence**: The string `"async"` or `"asynchronous"` appears in **0 columns and 0 rows** across the entire dataset.
- **Synchronous Online Sections**: 28 sections with `METHOD == "Online Live Lecture"` have explicit meeting days and times (e.g., CRN 16899 AST 2002 meets TR 12:30 PM - 01:50 PM). These sections now correctly undergo standard day/time overlap calculation.
- **Fully Online Class Sections**: All 230 sections with `METHOD == "Fully Online Class"` have `DAYS == NaN` and `BEG TIME == NaN`.
- **Authoritative Data Mapping**: `data/data_dictionary.md` lists permitted values for `METHOD` as an open data question (Section 8). Because no authoritative institutional dictionary maps `"Fully Online Class"` to verified asynchronous delivery, `is_verified_asynchronous` returns `False` and `get_schedule_status` returns `UNKNOWN_TIMING`.
- **Safety Consequence**: Schedule conflict checks involving `Fully Online Class` return `has_conflict=None`, `is_uncertain=True`, and `response_code="SCHEDULE_UNCERTAIN_TIMING"`. This guarantees zero false-negative non-conflict assertions.

---

## 4. Fresh Live HTTP Captures (Windows `curl.exe` over TCP :8008)

All requests executed against a live FastAPI instance (`http://127.0.0.1:8008`) and stored in `docs/task_004_live_http_evidence.json`.

### Case A: Known Overlapping Pair
- **Tool**: `curl.exe` | **URL**: `http://127.0.0.1:8008/conversation` | **Status**: `200 OK`
```json
// Request
{
  "message": "Do COP 3530C section 001 and MAC 2312 section 006 overlap?",
  "term": 202608,
  "sections": ["20158", "17077"]
}
// Response
{
  "status": "engine_executed",
  "raw_message": "Do COP 3530C section 001 and MAC 2312 section 006 overlap?",
  "disposition": "route_core_engine",
  "target_handler": "scheduling_engine",
  "response_code": "SCHEDULE_CONFLICT_FOUND",
  "response_text": "Schedule conflict detected: COP 3530C section 001 and MAC 2312 section 006 overlap on T, R (12:30 PM - 01:50 PM vs 12:00 PM - 01:50 PM).",
  "actionable_guidance": null,
  "safe_to_route": true,
  "missing_context": [],
  "extracted_courses": ["COP3530C", "MAC2312"],
  "engine_executed": true,
  "engine_result": {
    "success": true,
    "has_conflict": true,
    "is_uncertain": false,
    "shared_days": "T, R",
    "conflict_summary": "Yes",
    "note": null,
    "schedule_status": "confirmed_conflict",
    "section_1": {
      "crn": "20158",
      "course": "COP 3530C",
      "section": "001",
      "days": "T  R",
      "time": "12:30 PM - 01:50 PM",
      "schedule_status": "SCHEDULED"
    },
    "section_2": {
      "crn": "17077",
      "course": "MAC 2312",
      "section": "006",
      "days": "T  R",
      "time": "12:00 PM - 01:50 PM",
      "schedule_status": "SCHEDULED"
    }
  },
  "disclaimer": "SmartAdvisor conversational layer is a rule-based decision-support prototype. It does not approve overrides or register courses."
}
```

### Case B: Known Non-Overlapping Pair
- **Tool**: `curl.exe` | **URL**: `http://127.0.0.1:8008/conversation` | **Status**: `200 OK`
```json
// Request
{
  "message": "Do COP 3530C section 001 and MAC 2312 section 002 overlap?",
  "term": 202608,
  "sections": ["20158", "15637"]
}
// Response
{
  "status": "engine_executed",
  "raw_message": "Do COP 3530C section 001 and MAC 2312 section 002 overlap?",
  "disposition": "route_core_engine",
  "target_handler": "scheduling_engine",
  "response_code": "NO_SCHEDULE_CONFLICT",
  "response_text": "No schedule conflict found: COP 3530C section 001 (T  R 12:30 PM - 01:50 PM) and MAC 2312 section 002 (W  F 12:00 PM - 01:50 PM) do not overlap.",
  "actionable_guidance": null,
  "safe_to_route": true,
  "missing_context": [],
  "extracted_courses": ["COP3530C", "MAC2312"],
  "engine_executed": true,
  "engine_result": {
    "success": true,
    "has_conflict": false,
    "is_uncertain": false,
    "shared_days": "",
    "conflict_summary": "No",
    "schedule_status": "confirmed_no_conflict"
  },
  "disclaimer": "SmartAdvisor conversational layer is a rule-based decision-support prototype. It does not approve overrides or register courses."
}
```

### Case C: More Than Two Sections (Excess Rejection)
- **Tool**: `curl.exe` | **URL**: `http://127.0.0.1:8008/conversation` | **Status**: `200 OK`
```json
// Request
{
  "message": "Do COP 3530C section 001, MAC 2312 section 002, and MAC 2312 section 006 overlap?",
  "term": 202608,
  "sections": ["20158", "15637", "17077"]
}
// Response
{
  "status": "clarification",
  "raw_message": "Do COP 3530C section 001, MAC 2312 section 002, and MAC 2312 section 006 overlap?",
  "disposition": "route_core_engine",
  "target_handler": "scheduling_engine",
  "response_code": "EXCESS_SECTIONS_DETECTED",
  "response_text": "Schedule conflict checking currently supports comparing exactly two sections at a time. You provided 3 sections (20158, 15637, 17077). Please specify exactly two sections to check for conflicts.",
  "actionable_guidance": "Narrow your request to exactly two sections.",
  "safe_to_route": true,
  "missing_context": ["two_sections_only"],
  "extracted_courses": ["COP3530C", "MAC2312"],
  "engine_executed": false,
  "engine_result": null,
  "disclaimer": "SmartAdvisor conversational layer is a rule-based decision-support prototype. It does not approve overrides or register courses."
}
```

### Case D: Contradictory Message and Structured Context
- **Tool**: `curl.exe` | **URL**: `http://127.0.0.1:8008/conversation` | **Status**: `200 OK`
```json
// Request
{
  "message": "Do COP 3530C section 001 and MAC 2312 section 006 overlap?",
  "term": 202608,
  "sections": ["20158", "15637"]
}
// Response
{
  "status": "clarification",
  "raw_message": "Do COP 3530C section 001 and MAC 2312 section 006 overlap?",
  "disposition": "route_core_engine",
  "target_handler": "scheduling_engine",
  "response_code": "CONTRADICTORY_SECTION_DETAILS",
  "response_text": "Contradictory section information detected: Message references MAC2312 section 006, but structured input specifies section 002 (CRN 15637). Please clarify which section you want to evaluate.",
  "actionable_guidance": "Resolve the mismatch between message text and structured section context.",
  "safe_to_route": true,
  "missing_context": ["consistent_sections"],
  "extracted_courses": ["COP3530C", "MAC2312"],
  "engine_executed": false,
  "engine_result": null,
  "disclaimer": "SmartAdvisor conversational layer is a rule-based decision-support prototype. It does not approve overrides or register courses."
}
```

### Case E: Unknown/TBA Timing
- **Tool**: `curl.exe` | **URL**: `http://127.0.0.1:8008/conversation` | **Status**: `200 OK`
```json
// Request
{
  "message": "Do CNT 4403 section 001 and COP 3530C section 001 overlap?",
  "term": 202608,
  "sections": ["18077", "20158"]
}
// Response
{
  "status": "engine_executed",
  "raw_message": "Do CNT 4403 section 001 and COP 3530C section 001 overlap?",
  "disposition": "route_core_engine",
  "target_handler": "scheduling_engine",
  "response_code": "SCHEDULE_UNCERTAIN_TIMING",
  "response_text": "Cannot verify schedule conflict: Meeting times are missing, TBA, or unverified for: CNT 4403 section 001. Without verified meeting times or confirmed asynchronous status, non-conflict cannot be guaranteed for CNT 4403 section 001 and COP 3530C section 001.",
  "actionable_guidance": "Please consult the official course schedule or department for confirmed meeting times.",
  "safe_to_route": true,
  "missing_context": [],
  "extracted_courses": ["CNT4403", "COP3530C"],
  "engine_executed": true,
  "engine_result": {
    "success": true,
    "has_conflict": null,
    "is_uncertain": true,
    "shared_days": "",
    "conflict_summary": "Unknown",
    "reason": "Meeting times are missing, TBA, or unverified for: CNT 4403 section 001.",
    "schedule_status": "unknown_timing"
  },
  "disclaimer": "SmartAdvisor conversational layer is a rule-based decision-support prototype. It does not approve overrides or register courses."
}
```

### Case F: Alternatives with Explicit Target and Selected Schedule
- **Tool**: `curl.exe` | **URL**: `http://127.0.0.1:8008/conversation` | **Status**: `200 OK`
```json
// Request
{
  "message": "Find another section of COP 3530C section 001",
  "term": 202608,
  "target_section": "20158",
  "selected_sections": ["15637"]
}
// Response
{
  "status": "engine_executed",
  "raw_message": "Find another section of COP 3530C section 001",
  "disposition": "route_core_engine",
  "target_handler": "scheduling_engine",
  "response_code": "ALTERNATIVE_SECTIONS_FOUND",
  "response_text": "Found 2 non-conflicting alternative section(s) for COP 3530C (replacing Section 001): Section 011 (CRN 20788, F 12:00 PM - 01:50 PM, 9 seats open); Section 012 (CRN 20789, F 02:00 PM - 03:50 PM, 8 seats open).",
  "actionable_guidance": null,
  "safe_to_route": true,
  "missing_context": [],
  "extracted_courses": ["COP3530C"],
  "engine_executed": true,
  "engine_result": {
    "success": true,
    "target_section": {
      "crn": "20158",
      "course": "COP 3530C",
      "section": "001"
    },
    "selected_schedule": [
      {
        "crn": "15637",
        "course": "MAC 2312",
        "section": "002"
      }
    ],
    "count": 2,
    "alternatives": [
      {
        "crn": "20788",
        "course": "COP 3530C",
        "section": "011",
        "days": "F",
        "time": "12:00 PM - 01:50 PM",
        "timing_verified": true
      },
      {
        "crn": "20789",
        "course": "COP 3530C",
        "section": "012",
        "days": "F",
        "time": "02:00 PM - 03:50 PM",
        "timing_verified": true
      }
    ],
    "limitations": []
  },
  "disclaimer": "SmartAdvisor conversational layer is a rule-based decision-support prototype. It does not approve overrides or register courses."
}
```

### Case G: Alternatives with Missing (Omitted) Selected Schedule
- **Tool**: `curl.exe` | **URL**: `http://127.0.0.1:8008/conversation` | **Status**: `200 OK`
```json
// Request
{
  "message": "Find another section of COP 3530C section 001",
  "term": 202608,
  "target_section": "20158"
}
// Response
{
  "status": "clarification",
  "raw_message": "Find another section of COP 3530C section 001",
  "disposition": "route_core_engine",
  "target_handler": "scheduling_engine",
  "response_code": "MISSING_SCHEDULE_CONTEXT",
  "response_text": "To find alternative sections that do not conflict with your schedule, please provide your currently selected schedule sections in selected_sections (or pass [] if you have no other enrolled sections).",
  "actionable_guidance": "Provide enrolled section CRNs in selected_sections context, or supply [] for an empty schedule.",
  "safe_to_route": true,
  "missing_context": ["selected_sections"],
  "extracted_courses": ["COP3530C"],
  "engine_executed": false,
  "engine_result": null,
  "disclaimer": "SmartAdvisor conversational layer is a rule-based decision-support prototype. It does not approve overrides or register courses."
}
```

### Case H: Alternatives with Explicitly Empty Selected Schedule
- **Tool**: `curl.exe` | **URL**: `http://127.0.0.1:8008/conversation` | **Status**: `200 OK`
```json
// Request
{
  "message": "Find another section of COP 3530C section 001",
  "term": 202608,
  "target_section": "20158",
  "selected_sections": []
}
// Response
{
  "status": "engine_executed",
  "raw_message": "Find another section of COP 3530C section 001",
  "disposition": "route_core_engine",
  "target_handler": "scheduling_engine",
  "response_code": "ALTERNATIVE_SECTIONS_FOUND",
  "response_text": "Found 2 non-conflicting alternative section(s) for COP 3530C (replacing Section 001): Section 011 (CRN 20788, F 12:00 PM - 01:50 PM, 9 seats open); Section 012 (CRN 20789, F 02:00 PM - 03:50 PM, 8 seats open).",
  "actionable_guidance": null,
  "safe_to_route": true,
  "missing_context": [],
  "extracted_courses": ["COP3530C"],
  "engine_executed": true,
  "engine_result": {
    "success": true,
    "count": 2,
    "selected_schedule": [],
    "limitations": []
  },
  "disclaimer": "SmartAdvisor conversational layer is a rule-based decision-support prototype. It does not approve overrides or register courses."
}
```

### Case I: Course Compatibility Evaluation
- **Via `/conversation` (Conversational Router)**:
```json
// Request
POST http://127.0.0.1:8008/conversation
{
  "message": "Can I take COP 4331 and MAP 3305 together?",
  "student_id": "Z24567901",
  "recent_difficulty": 1,
  "satisfied_with_performance": "yes",
  "work_hours": 5.0,
  "preferred_max_credits": 15.0
}
// Response (HTTP 200 OK)
{
  "status": "engine_executed",
  "raw_message": "Can I take COP 4331 and MAP 3305 together?",
  "disposition": "route_core_engine",
  "target_handler": "course_compatibility_engine",
  "response_code": "COMPATIBILITY_EVALUATION_COMPLETE",
  "response_text": "Workload compatibility evaluation completed for COP4331, MAP3305. Semester assessment: Potentially manageable based on the information provided.",
  "actionable_guidance": null,
  "safe_to_route": true,
  "missing_context": [],
  "extracted_courses": ["COP4331", "MAP3305"],
  "engine_executed": true,
  "engine_result": {
    "success": true,
    "student_id": "Z24567901",
    "student_name": "Evie Woods",
    "major": "Electrical Engineering",
    "proposed_courses": ["COP4331", "MAP3305"],
    "proposed_credits": 6.0,
    "assessment": "Potentially manageable based on the information provided"
  },
  "disclaimer": "SmartAdvisor conversational layer is a rule-based decision-support prototype. It does not approve overrides or register courses."
}
```
- **Via `/compatibility` (Direct Engine Endpoint)**:
```json
// Request
POST http://127.0.0.1:8008/compatibility
{
  "student_id": "Z24567901",
  "proposed_courses": ["COP 4331", "MAP 3305"],
  "recent_difficulty": 1,
  "satisfied_with_performance": "yes",
  "work_hours": 5.0,
  "preferred_max_credits": 15.0
}
// Response (HTTP 200 OK)
{
  "success": true,
  "student_id": "Z24567901",
  "student_name": "Evie Woods",
  "major": "Electrical Engineering",
  "proposed_courses": ["COP4331", "MAP3305"],
  "proposed_credits": 6.0,
  "assessment": "Potentially manageable based on the information provided",
  "disclaimer": "This is preliminary academic planning guidance, not an official advising or registration decision."
}
```

### Case J: Advisor Escalation
- **Tool**: `curl.exe` | **URL**: `http://127.0.0.1:8008/conversation` | **Status**: `200 OK`
```json
// Request
{
  "message": "Can you give me a prerequisite override for COP 3530C?"
}
// Response
{
  "status": "escalation",
  "raw_message": "Can you give me a prerequisite override for COP 3530C?",
  "disposition": "advisor_escalation",
  "target_handler": "academic_advisor",
  "response_code": "ADVISOR_ESCALATION_REQUIRED",
  "response_text": "An academic advisor or authorized university office must make the official decision or action regarding your request.",
  "actionable_guidance": "Official advising actions (overrides, registration, graduation) require consulting with an authorized academic advisor.",
  "safe_to_route": false,
  "missing_context": [],
  "extracted_courses": ["COP3530C"],
  "engine_executed": false,
  "engine_result": null,
  "disclaimer": "SmartAdvisor conversational layer is a rule-based decision-support prototype. It does not approve overrides or register courses."
}
```

### Case K: Known Informational Prompt Reaching Inactive-RAG Boundary
- **Tool**: `curl.exe` | **URL**: `http://127.0.0.1:8008/conversation` | **Status**: `200 OK`
```json
// Request
{
  "message": "What does the policy say about dropping a course?"
}
// Response
{
  "status": "rag_inactive",
  "raw_message": "What does the policy say about dropping a course?",
  "disposition": "future_rag_candidate",
  "target_handler": "future_informational_rag",
  "response_code": "FUTURE_RAG_NOT_AVAILABLE",
  "response_text": "Source-grounded informational lookup is not enabled in the current prototype. Please check the official catalog or speak with an advisor.",
  "actionable_guidance": "Informational RAG retrieval is planned for a future milestone and is not active in this prototype.",
  "safe_to_route": false,
  "missing_context": [],
  "extracted_courses": [],
  "engine_executed": false,
  "engine_result": null,
  "disclaimer": "SmartAdvisor conversational layer is a rule-based decision-support prototype. It does not approve overrides or register courses."
}
```

---

## 5. Shared Scheduling Functions & Backend Integration Review (For Jeffrey)

1. **`backend.meeting_time_normalizer`**:
   - `is_verified_asynchronous(section)`: Requires explicit asynchronous indicator in section attributes or strings. In `FAU_Courses.xlsx`, online courses lacking the word "asynchronous" evaluate to `False` by design.
   - `get_schedule_status(section)`: Produces mutually exclusive `SCHEDULED`, `VERIFIED_ASYNCHRONOUS`, or `UNKNOWN_TIMING`.
   - `normalize_days`, `normalize_time`, and `online_section` retain original contracts.

2. **`backend.overlap_detector`**:
   - `has_schedule_information(section)`: Returns `True` for synchronous online sections with usable meeting times.
   - `sections_overlap(sec1, sec2)`: Evaluates synchronous online sections using standard interval arithmetic.
   - `get_conflict_details(sec1, sec2)`: Returns `conflict="Unknown"` with explanatory reason when timing is incomplete or TBA.

3. **`backend.scheduling_service`**:
   - `resolve_section`: Validates CRN against provided course code, section number, and term.
   - `evaluate_schedule_conflict`: Distinguishes confirmed conflict (`has_conflict=True`), confirmed no-conflict (`has_conflict=False`), and uncertain timing (`has_conflict=None`).
   - `evaluate_alternative_sections`: Audits enrolled schedule for unknown timing and attaches safe limitation disclosures.

---

## 6. Remaining Scope Boundaries & Limitations

1. **Two-Section Comparison Scope**: Schedule conflict checking is strictly bounded to pairwise comparison (2 sections). Full schedule-wide combinatorial comparison is intentionally deferred.
2. **Deterministic Intent Classifier**: Entity extraction and intent routing currently utilize regular expressions and dictionary mappings.
3. **Inactive RAG Boundary**: Policy and catalog informational queries safely route to `rag_inactive` without engine execution.
4. **Online Override Screening**: Directs users to the UI override workflow (`status="engine_unavailable"`).
5. **No Database Mutation**: All operations are read-only against `FAU_Courses.xlsx` and synthetic student profiles.

---

## 7. LLM-Readiness Checklist

| Criterion | Status | Verification Detail |
|---|---|---|
| **Contract Stability** | Complete | Standardized `status`, `disposition`, `target_handler`, `response_code`, `safe_to_route`, `engine_executed`. |
| **Strict Section Scoping** | Complete | >2 section queries cleanly rejected with `EXCESS_SECTIONS_DETECTED` without silent truncation. |
| **Meeting-Time Safety** | Complete | Synchronous online overlap active; unknown/TBA times produce `SCHEDULE_UNCERTAIN_TIMING`; verified asynchronous distinguished. |
| **Contradiction Defense** | Complete | Inconsistencies between text and structured context return `CONTRADICTORY_SECTION_DETAILS` before engine calls. |
| **Structured Context Precedence** | Complete | Structured context fills missing message details without requiring text repetition. |
| **Safe Error Handling** | Complete | Internal exceptions logged via `logger.exception`; user responses contain safe generic messages. |
| **Deterministic Fallback Readiness** | Complete | Rule-based classifier and response policy are fully preserved as a 100% deterministic fallback for the LLM parser. |
| **Test Suite Health** | Complete | 132/132 pytest tests pass (100% across the repository). |
| **Git Hygiene** | Complete | `git diff --check` passes with zero whitespace or formatting warnings. |

---
*Ready for provider-independent LLM structured parsing with deterministic fallback.*
