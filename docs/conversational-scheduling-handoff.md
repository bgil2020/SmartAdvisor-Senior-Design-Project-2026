# Conversational Scheduling Handoff & Contract Stabilization (TASK-003)

## 1. Overview & Checkpoint Baseline
- **Repository**: `SmartAdvisor-Senior-Design-Project-2026`
- **Branch**: `feature/conversational-scheduling-integration`
- **Baseline Checkpoint (TASK-002)**: Commit `8b327aef42277fb4a937f3ba51f9c1ba37387373`
- **Task Objective**: Complete bounded conversational scheduling stabilization, timing safety, and backend contract readiness for the upcoming LLM-parser task without expanding scope or adding unapproved features.

---

## 2. Hardened Architecture & Risk Fixes Summary

### Risk A: Prevention of Silent Section Truncation
- **Scope Restriction**: Schedule conflict checking remains strictly bounded to **exactly two sections**.
- **Fix**: Requests referencing more than two sections in structured input (`req.sections > 2`) or free-text query (`entities.course_section_pairs > 2` or `entities.crns > 2`) are immediately rejected/clarified with `response_code="EXCESS_SECTIONS_DETECTED"`, `status="clarification"`, `safe_to_route=True`, and `engine_executed=False`.
- **Elimination of False Negatives**: Previously, providing 3 sections where (Section 1, Section 2) did not conflict but (Section 1, Section 3) conflicted caused silent truncation to `[:2]`, resulting in a false `NO_SCHEDULE_CONFLICT`. This false negative is now completely prevented.

### Risk B: Correct Meeting-Time Handling & Timing Safety
Sections are categorized into three mutually exclusive scheduling states:
1. `SCHEDULE_STATUS_SCHEDULED ("SCHEDULED")`: Section contains usable days and start/end meeting times (`start_mins < end_mins`). Both in-person and synchronous online sections participate fully in time overlap calculation.
2. `SCHEDULE_STATUS_ASYNCHRONOUS ("VERIFIED_ASYNCHRONOUS")`: Section is explicitly verified as asynchronous online delivery (has explicit `asynchronous` flag or method/title/delivery indicates asynchronous). Has no fixed meeting times and does not conflict with scheduled classes.
3. `SCHEDULE_STATUS_UNKNOWN ("UNKNOWN_TIMING")`: Incomplete, missing, or TBA meeting times where asynchronous status cannot be verified (e.g. in-person courses with TBA times, or online courses without confirmed asynchronous delivery).
- **Online delivery alone does not imply asynchronous.**
- **Missing times alone do not imply asynchronous.**
- **Insufficient data does not produce a verified "no conflict."** Instead, when timing is unknown or TBA, the engine returns `has_conflict=None`, `is_uncertain=True`, and the conversational response returns `response_code="SCHEDULE_UNCERTAIN_TIMING"`.
- **Alternative Section Search Timing Safety**:
  - If candidate section timing is unverified/TBA, it is flagged with `timing_verified=False` and safe limitations are returned.
  - If the student's enrolled schedule (`selected_sections`) contains sections with unknown/TBA timing (e.g. CRN 18077 CNT 4403), the engine records `has_unknown_schedule=True` and discloses that alternative sections cannot be guaranteed to avoid conflict with unverified enrolled classes.

### Risk C: Handling Contradictory Inputs & Context
1. **Internal Field Consistency**: `resolve_section` cross-checks supplied CRN against any supplied course, section, and term fields. If CRN 20158 (COP 3530C section 001) is passed with `course="MAC 2312"` or `section="002"`, it returns an explicit error (`"Contradictory section details..."`).
2. **Message vs Structured Context Cross-Checking**: The router cross-checks explicit message references against structured context. If message text references section 006 (or CRN 17077) but structured sections provide section 002 (CRN 15637), the router returns targeted clarification before engine execution (`response_code="CONTRADICTORY_SECTION_DETAILS"`).
3. **Structured Context Fills Missing Details**: If message text does not repeat course or section numbers (e.g., "Do these two courses overlap?"), structured sections fill the missing details cleanly without requiring textual repetition.
4. **Unsupported Preferences Disclosure**: If user prompt requests unsupported preferences (specific instructors/professors, morning/evening times, online-only modality), a clear limitation disclosure is attached to the response.

### Risk D: Execution-Field Semantics Stability
- `engine_executed`: Strictly `True` if and only if the underlying engine function was executed to evaluate the query. Remains `False` for clarifications, escalations, inactive RAG queries, unsupported queries, or validation failures prior to engine invocation.
- `safe_to_route`: Strictly reflects whether the query belongs to a supported core handler and was routed (`True` for routed core queries even if clarification/not-found occurs inside the handler; `False` for general classifier-level clarification, advisor escalation, inactive RAG, or unsupported scope).
- `status`: Standardized to `engine_executed`, `clarification`, `escalation`, `rag_inactive`, `unsupported`, `engine_unavailable`, or `engine_error`.

---

## 3. Representative Live HTTP Request and Response Captures

### Case 1: SUCCESS - Real Overlapping Conflict
**Request**:
```json
POST /conversation
{
  "message": "Do COP 3530C section 001 and MAC 2312 section 006 overlap?",
  "sections": ["20158", "17077"]
}
```
**Response (HTTP 200)**:
```json
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
      "title": "Data Struc and Algrthm Anlys",
      "days": "T  R",
      "time": "12:30 PM - 01:50 PM",
      "method": "In-Person",
      "campus": "Boca Raton",
      "term": 202608,
      "seats_remaining": 17,
      "instructor": "Nojoumian, Mehrdad",
      "schedule_status": "SCHEDULED"
    },
    "section_2": {
      "crn": "17077",
      "course": "MAC 2312",
      "section": "006",
      "title": "Calculus-Analytic Geometry 2",
      "days": "T  R",
      "time": "12:00 PM - 01:50 PM",
      "method": "In-Person",
      "campus": "Boca Raton",
      "term": 202608,
      "seats_remaining": 7,
      "instructor": "Locke, Stephen",
      "schedule_status": "SCHEDULED"
    }
  },
  "disclaimer": "SmartAdvisor conversational layer is a rule-based decision-support prototype. It does not approve overrides or register courses."
}
```

### Case 2: SUCCESS - Confirmed Non-Overlapping Pair
**Request**:
```json
POST /conversation
{
  "message": "Do COP 3530C section 001 and MAC 2312 section 002 overlap?",
  "sections": ["20158", "15637"]
}
```
**Response (HTTP 200)**:
```json
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
    "note": null,
    "schedule_status": "confirmed_no_conflict",
    "section_1": {
      "crn": "20158",
      "course": "COP 3530C",
      "section": "001",
      "days": "T  R",
      "time": "12:30 PM - 01:50 PM",
      "schedule_status": "SCHEDULED"
    },
    "section_2": {
      "crn": "15637",
      "course": "MAC 2312",
      "section": "002",
      "days": "W  F",
      "time": "12:00 PM - 01:50 PM",
      "schedule_status": "SCHEDULED"
    }
  },
  "disclaimer": "SmartAdvisor conversational layer is a rule-based decision-support prototype. It does not approve overrides or register courses."
}
```

### Case 3: CLARIFICATION - Excess Sections (>2)
**Request**:
```json
POST /conversation
{
  "message": "Do COP 3530C section 001, MAC 2312 section 002, and MAC 2312 section 006 overlap?",
  "sections": ["20158", "15637", "17077"]
}
```
**Response (HTTP 200)**:
```json
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

### Case 4: CLARIFICATION - Contradictory Inputs (Message vs Structured Sections)
**Request**:
```json
POST /conversation
{
  "message": "Do COP 3530C section 001 and MAC 2312 section 006 overlap?",
  "sections": ["20158", "15637"]
}
```
**Response (HTTP 200)**:
```json
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

### Case 5: UNCERTAINTY - Missing/TBA Meeting Times
**Request**:
```json
POST /conversation
{
  "message": "Do CNT 4403 section 001 and COP 3530C section 001 overlap?",
  "sections": ["18077", "20158"]
}
```
**Response (HTTP 200)**:
```json
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
    "schedule_status": "unknown_timing",
    "section_1": {
      "crn": "18077",
      "course": "CNT 4403",
      "section": "001",
      "days": "",
      "time": "Unscheduled / Online",
      "schedule_status": "UNKNOWN_TIMING"
    },
    "section_2": {
      "crn": "20158",
      "course": "COP 3530C",
      "section": "001",
      "days": "T  R",
      "time": "12:30 PM - 01:50 PM",
      "schedule_status": "SCHEDULED"
    }
  },
  "disclaimer": "SmartAdvisor conversational layer is a rule-based decision-support prototype. It does not approve overrides or register courses."
}
```

### Case 6: UNCERTAINTY - Alternative Section Search with TBA Enrolled Course
**Request**:
```json
POST /conversation
{
  "message": "Find another section of COP 3530C section 001",
  "target_section": "20158",
  "selected_sections": ["18077"]
}
```
**Response (HTTP 200)**:
```json
{
  "status": "engine_executed",
  "raw_message": "Find another section of COP 3530C section 001",
  "disposition": "route_core_engine",
  "target_handler": "scheduling_engine",
  "response_code": "ALTERNATIVE_SECTIONS_FOUND",
  "response_text": "Found 2 non-conflicting alternative section(s) for COP 3530C (replacing Section 001): Section 011 (CRN 20788, F 12:00 PM - 01:50 PM, 9 seats open); Section 012 (CRN 20789, F 02:00 PM - 03:50 PM, 8 seats open). Limitation: Current schedule contains section(s) with unverified or TBA meeting times: CNT 4403 section 001. Cannot guarantee alternative sections avoid conflict with unverified sections.",
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
        "crn": "18077",
        "course": "CNT 4403",
        "section": "001",
        "schedule_status": "UNKNOWN_TIMING"
      }
    ],
    "count": 2,
    "has_unknown_schedule": true,
    "limitations": [
      "Current schedule contains section(s) with unverified or TBA meeting times: CNT 4403 section 001. Cannot guarantee alternative sections avoid conflict with unverified sections."
    ]
  },
  "disclaimer": "SmartAdvisor conversational layer is a rule-based decision-support prototype. It does not approve overrides or register courses."
}
```

---

## 4. Shared Scheduling Functions & Backend Integration Review (For Jeffrey)

The following shared scheduling components were audited and hardened to ensure consistent behavior across all backend callers (`backend/api.py`, `backend/overlap_detector.py`, `backend/alternative_section_search.py`, `backend/scheduling_service.py`):

1. **`backend.meeting_time_normalizer`**:
   - Added `is_verified_asynchronous(section)`: Explicitly checks for verified asynchronous indicator (in method, title, or delivery mode). Prevents treating general online courses or missing times as automatically asynchronous.
   - Added `get_schedule_status(section)`: Returns `SCHEDULED`, `VERIFIED_ASYNCHRONOUS`, or `UNKNOWN_TIMING`.
   - Kept `normalize_days`, `normalize_time`, and `online_section` backward-compatible.

2. **`backend.overlap_detector`**:
   - `has_schedule_information(section)`: Previously returned `False` unconditionally for any online section. Now returns `True` for synchronous online sections with usable meeting times (`SCHEDULE_STATUS_SCHEDULED`).
   - `sections_overlap(sec1, sec2)`: Removed blanket online bypass. Synchronous online sections now participate in standard time overlap calculations.
   - `get_conflict_details(sec1, sec2)`: When either section has `UNKNOWN_TIMING`, returns `conflict="Unknown"` with explanatory reason. Insufficient data no longer produces a false `"No"` conflict.

3. **`backend.alternative_section_search`**:
   - Synchronous online candidate sections participate in conflict detection against enrolled sections.
   - Retains full compatibility with existing `GET /alternatives` endpoint.

4. **`backend.scheduling_service`**:
   - `resolve_section`: Added strict internal validation when CRN is passed alongside course, section, or term.
   - `evaluate_schedule_conflict`: Distinguishes confirmed conflict (`has_conflict=True`), confirmed no-conflict (`has_conflict=False`), and uncertain timing (`has_conflict=None`).
   - `evaluate_alternative_sections`: Audits enrolled schedule for unknown timing and attaches safe limitation disclosures.

---

## 5. Remaining Scope Boundaries & Limitations

1. **Two-Section Comparison Scope**: Schedule conflict checking is intentionally bounded to exactly two sections. Cross-schedule combinatorial comparison is deferred.
2. **Deterministic Intent Classifier**: The conversational assistant currently uses rule-based entity extraction and keyword/pattern classification.
3. **Inactive RAG Boundary**: Informational and catalog syllabus queries remain safely inactive (`status="rag_inactive"`, `safe_to_route=False`, `engine_executed=False`).
4. **Online Override Form**: Screenings are directed to the UI component (`status="engine_unavailable"`).
5. **No Database Mutation**: All operations are read-only against `FAU_Courses.xlsx` and synthetic student profiles.

---

## 6. LLM-Readiness Checklist

| Criterion | Status | Verification Detail |
|---|---|---|
| **Contract Stability** | Complete | Standardized `status`, `disposition`, `target_handler`, `response_code`, `safe_to_route`, `engine_executed`. |
| **Strict Section Scoping** | Complete | >2 section queries are cleanly rejected with `EXCESS_SECTIONS_DETECTED` without silent truncation. |
| **Meeting-Time Safety** | Complete | Synchronous online overlap active; unknown/TBA times produce `SCHEDULE_UNCERTAIN_TIMING`; verified asynchronous distinguished. |
| **Contradiction Defense** | Complete | Inconsistencies between text and structured context return `CONTRADICTORY_SECTION_DETAILS` before engine calls. |
| **Structured Context Precedence** | Complete | Structured context fills missing message details without requiring message repetition. |
| **Safe Error Handling** | Complete | Internal exceptions are logged via `logger.exception`; user-facing responses contain safe generic messages. |
| **Deterministic Fallback Readiness** | Complete | Rule-based classifier and response policy are fully preserved to serve as a 100% deterministic fallback for the LLM parser. |
| **Test Suite Health** | Complete | 132/132 pytest tests pass (100% passing across the entire repository). |
| **Git Hygiene** | Complete | `git diff --check` passes with zero whitespace or formatting warnings. |

---
*Ready for provider-independent LLM structured parsing with deterministic fallback.*
