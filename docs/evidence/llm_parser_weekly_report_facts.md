# LLM Structured Parser Implementation & Fallback Fact Sheet

**Document Reference:** `docs/evidence/llm_parser_weekly_report_facts.md`
**Associated Task:** TASK-011 (Handoff for Second Weekly Report Task)
**Parent Task ID:** TASK-005 / TASK-009 / TASK-010
**Repository:** `bgil2020/SmartAdvisor-Senior-Design-Project-2026`
**Branch:** `feature/llm-structured-parser`
**Base Commit (Merged Main Checkpoint):** `4ad964f20fc6e20623c75cf92e8bfa30aef361af`

---

## A. Task Identity and Status

- **Existing Planner Task Title:** "Implement LLM structured intent and entity extraction with deterministic fallback"
- **Work Dates:** October 18, 2026
- **Recorded Timestamp of Evidence:** `2026-10-19T02:02:19Z` (Corresponds to October 18, 2026 at 10:02:19 PM Eastern Daylight Time [EDT, UTC-4]).
- **Status Classification:**
  - **Architecture & Source Implementation:** **Completed** (adapter, canonical contract, grounding, fallback dispatcher, response policy integration, observability metadata).
  - **Offline Test Verification:** **Completed** (166 passing backend tests, 34 dedicated parser/grounding tests, 28/28 deterministic benchmark tests).
  - **Live Real-Provider Verification:** **Pending** (real provider call returned `402 RESOURCE_EXHAUSTED` due to account prepayment credits depleted; automatic fallback was verified through the running HTTP endpoint).
- **Hours Worked:** Not recorded / not invented (per repository reporting guidelines).

---

## B. Concrete Contribution

This second task specifically introduced:
1. **Provider-Independent Parser Interface & Gemini Adapter:**
   - Abstract `BaseConversationalParser` interface.
   - `GeminiStructuredParser` concrete adapter utilizing official `google-genai` Python SDK (`google-genai>=2.0.0`) with schema-constrained JSON output (`GeminiIntentSchema`).
2. **Shared Typed Parsing Representation (`CanonicalParsingResult`):**
   - Uniform data contract shared identically by the deterministic regex parser and LLM parser.
   - Decouples extraction from deterministic advising safety policy.
3. **Structured-Output Validation & Strict Entity Grounding:**
   - **Boundary-Aware Course Grounding (`_is_course_grounded`):** Requires complete, boundary-aware normalized course identifiers (`[A-Z]{3}\d{4}[A-Z]?`). Preserves suffixes strictly (`COP3530` does not ground `COP3530C`, and vice versa). Rejects combinations of department from one course and digits from another. Never uses unreferenced past `recent_courses` to ground newly proposed courses. Nonexistent catalog courses explicitly typed by students pass grounding to reach the catalog resolver.
   - **Strict Course-Section Association Grounding (`_is_pair_grounded`):** Eliminates zero-stripped digit anywhere matching. Requires valid binding syntax (e.g. `COP 3530C-001`, `COP 3530 section 001`, `section 001 of COP 3530`) or structured context dicts containing both course and section. Rejects swapped or cross-assigned section pairings.
   - **Standalone Section & Constraint Grounding:** Rejects course-number digits grounding invented sections; validates standalone `section_identifiers`, `preferred_days`, and `modality_preference`.
4. **Automatic Deterministic Fallback (`HybridConversationalParser`):**
   - Dispatches to `GeminiStructuredParser` when `CONVERSATIONAL_PARSER_MODE=hybrid`.
   - Safely catches all provider failures (missing key, transport timeout, rate limit / 402 / 429 quota exhaustion, schema validation failure, ungrounded entity detection) and falls back immediately to deterministic parsing without crashing, retrying, or throwing HTTP 500s.
5. **Integration with Existing Policy & Authoritative Engines:**
   - Plugs directly into `handle_conversation` in `backend/conversational_router.py`.
   - Preserves all safety gates: advisor escalation triggers regardless of parser interpretation; excess section safeguard triggers before engine invocation.
   - Note: The underlying course compatibility and scheduling engines were **not** newly built in this task; they belong to existing team work and TASK-003/TASK-004 integration.
6. **Observability & Metadata:**
   - Exposes `parser_source` (`"llm"`, `"deterministic"`, or `"fallback"`), `fallback_used` (`bool`), `fallback_reason` (`str`), and `model_id` (`str`) in `ConversationResponse`.
7. **Project Virtual Environment & Configuration:**
   - Setup and verification of isolated project virtual environment (`.venv`) under Python 3.12, ensuring no global package pollution.

---

## C. Exact Implementation References

| Feature | File Path | Class / Function Name | Line Numbers | Role & Responsibility |
| :--- | :--- | :--- | :--- | :--- |
| **Typed Contract** | `backend/app/conversational/parser_contract.py` | `CanonicalParsingResult`, `CourseSectionPair`, `ScheduleConstraints` | Lines 33–85 | Normalized parsing representation consumed by downstream response policy. |
| **Abstract Parser** | `backend/app/conversational/gemini_parser.py` | `BaseConversationalParser` | Lines 138–145 | Provider-agnostic abstract base interface for conversational intent/entity parsers. |
| **Gemini Adapter** | `backend/app/conversational/gemini_parser.py` | `GeminiStructuredParser` | Lines 147–309 | GenAI SDK adapter with schema constraints, bounded execution, and validation. |
| **Course Grounding** | `backend/app/conversational/gemini_parser.py` | `_is_course_grounded`, `_extract_message_courses` | Lines 318–365 | Boundary-aware course extraction, exact suffix matching, and unreferenced context rejection. |
| **Pair Grounding** | `backend/app/conversational/gemini_parser.py` | `_is_pair_grounded`, `_extract_bound_course_section_pairs`, `_sections_match` | Lines 367–470 | Association syntax validation, leading zero preservation, and swapped-pair rejection. |
| **Section & Constraints** | `backend/app/conversational/gemini_parser.py` | `_is_section_grounded`, `_is_crn_grounded`, `_is_day_grounded`, `_is_modality_grounded` | Lines 472–609 | Standalone section, CRN, day, and modality grounding checks against user query text. |
| **Hybrid Dispatcher** | `backend/app/conversational/hybrid_parser.py` | `HybridConversationalParser`, `parse_query` | Lines 99–179 | Manages parser execution mode, bounds latency, and catches exceptions for deterministic fallback. |
| **Reason Sanitizer** | `backend/app/conversational/hybrid_parser.py` | `_sanitize_fallback_reason` | Lines 152–171 | Sanitizes error strings to prevent leaking keys, URLs, or internal stack traces into responses. |
| **Router Integration** | `backend/conversational_router.py` | `handle_conversation`, `_build_response` | Lines 110–144 | Routes query through hybrid parser, enforces safety gates, and injects observability metadata. |

---

## D. Final Test Evidence

All tests executed using the project virtual environment (`D:\Projects\SmartAdvisor-Senior-Design-Project-2026\.venv\Scripts\python.exe`):

| Test Suite / Target | Exact Command Line | Exit Code | Result Summary | Notes / Warnings |
| :--- | :--- | :---: | :---: | :--- |
| **Dedicated LLM Parser Suite** | `.\.venv\Scripts\python.exe -m pytest tests/test_llm_parser.py -v` | `0` | **34 passed** in 1.98s | Covers contract, mocked parser, fallback triggers, routing, and 11 new grounding regressions. (1 Starlette deprecation warning). |
| **Scheduling Safety Suite** | `.\.venv\Scripts\python.exe -m pytest tests/test_scheduling_risk_investigation.py tests/test_conversational_api.py -v` | `0` | **29 passed** in 2.13s | Verifies 3-section freetext safeguards, synchronous/asynchronous overlap, and context contradictions. |
| **Full Backend Suite** | `.\.venv\Scripts\python.exe -m pytest -v` | `0` | **166 passed** in 4.99s | Complete regression suite across all backend modules. |
| **Deterministic Benchmark** | `.\.venv\Scripts\python.exe -m pytest backend/tests/test_dataset_evaluation.py -s -v` | `0` | **28/28 passed (100.0%)** in 0.02s | Evaluates deterministic intent classifier accuracy on labeled test prompts (does not measure Gemini or entity extraction). |
| **Git Diff Whitespace Check** | `git diff --check` | `0` | **0 errors** | Clean formatting across all touched tracked files. |

*Disclaimer:* Passing tests demonstrate compliance with tested assertions and regression cases; they do not constitute mathematical proof of zero defects.

---

## E. Live Execution Findings

Evidence captured from running backend server via `scripts/verify_task_010_live_http.py` and saved in `docs/task_010_live_http_evidence.json`:

> **Key Finding:** No successful live Gemini parsing response was demonstrated. The configured model (`gemini-3.8-flash`) encountered `402 RESOURCE_EXHAUSTED` on the provided account key. The system safely fell back to deterministic execution in every case.

| Case ID | Message / Context Reference | `parser_source` & `fallback_used` | `response_code` & `engine_executed` | Actual Observed Result | Recorded Latency (Individual Run) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`DET-01`** | `Can I take COP 4331 and MAP 3305 together?` with synthetic profile `Z24567901` | `parser_source: deterministic`<br>`fallback_used: False` | `COMPATIBILITY_EVALUATION_COMPLETE`<br>`engine_executed: True` | Pure offline mode without provider call; compatibility engine successfully evaluated workload. | `102.8ms` |
| **`DET-02`** | `Do COP 3530C section 001 and MAC 2312 section 006 overlap?`, `term: 202608` | `parser_source: deterministic`<br>`fallback_used: False` | `SCHEDULE_CONFLICT_FOUND`<br>`engine_executed: True` | Pure offline mode without provider call; scheduling engine confirmed meeting time overlap on T, R. | `122.7ms` |
| **`HYB-01`** | `Would enrolling in both COP 4331 and MAP 3305 exhaust my weekly capacity?` with `Z24567901` | `parser_source: fallback`<br>`fallback_used: True` | `AMBIGUOUS_REQUEST`<br>`engine_executed: False` | Provider call attempted (`provider_called: True`), returned 402; fallback deterministic parser did not recognize paraphrase keywords, safely returning clarification. | `988.8ms` |
| **`HYB-02`** | `Can I take COP 4331 and MAP 3305 together?` with `Z24567901` | `parser_source: fallback`<br>`fallback_used: True` | `COMPATIBILITY_EVALUATION_COMPLETE`<br>`engine_executed: True` | Provider call attempted (`provider_called: True`), returned 402; fallback deterministic parser recognized courses and compatibility intent, successfully executing compatibility engine. | `703.3ms` |
| **`HYB-03`** | `Do COP 3530C section 001 and MAC 2312 section 006 overlap?`, `term: 202608` | `parser_source: fallback`<br>`fallback_used: True` | `SCHEDULE_CONFLICT_FOUND`<br>`engine_executed: True` | Provider call attempted (`provider_called: True`), returned 402; fallback deterministic parser extracted sections, successfully executing scheduling conflict engine. | `871.5ms` |
| **`HYB-04`** | `Can I take COP 3530?` | `parser_source: fallback`<br>`fallback_used: True` | `AMBIGUOUS_REQUEST`<br>`engine_executed: False` | Provider call attempted (`provider_called: True`), returned 402; fallback returned safe clarification due to single course. | `716.1ms` |
| **`HYB-05`** | `Please approve an official prerequisite override for COP 3530 so I can graduate.` | `parser_source: fallback`<br>`fallback_used: True` | `ADVISOR_ESCALATION_REQUIRED`<br>`engine_executed: False` | Reached hybrid endpoint; safety policy correctly escalated to academic advisor without core engine execution. | `628.1ms` |
| **`HYB-06`** | `What does the university catalog policy say about course withdrawal prerequisites?` | `parser_source: fallback`<br>`fallback_used: True` | `FUTURE_RAG_NOT_AVAILABLE`<br>`engine_executed: False` | Reached hybrid endpoint; correctly categorized as inactive informational candidate without core engine execution. | `649.8ms` |

*Note on Latency:* Latencies are single-request observations from the local verification harness, not statistical benchmarks.
*Note on `provider_called`:* Recorded as `True` when the execution reached the hybrid handler attempting a network call to Google GenAI prior to catching the provider error.

---

## F. Blocker and Next Steps

- **Observed Blocker:**
  - When communicating with Google GenAI API (`gemini-3.8-flash`), the API returned:
    `402 RESOURCE_EXHAUSTED: Your prepayment credits are depleted. Please go to AI Studio at https://ai.studio/projects to manage your project and billing. Learn more at https://ai.google.dev/gemini-api/docs/billing#prepay.`
  - Per owner constraints, no billing changes or paid model selections were made.
- **Recommended Action for Next Week:**
  1. Access [Google AI Studio](https://ai.studio/projects) using the authorized account.
  2. Resolve the prepayment/credit status or generate an API key tied to an active free-tier project.
  3. Execute a single bounded test with `scripts/verify_task_010_live_http.py` to capture real `parser_source: "llm"` parsing responses.
  4. Finalize the task and submit the review PR.

---

## G. Evidence Provenance

| Evidence Category | Source / Execution Method | Status |
| :--- | :--- | :--- |
| **Automated Test Suite (166 tests)** | Agent-executed via `.venv` Python in Antigravity environment | **Verified** |
| **Mocked Provider Integration Tests** | `tests/test_llm_parser.py` (simulating SDK responses and errors) | **Verified** |
| **Actual Provider Error Evidence** | Direct SDK call to Google GenAI receiving `402 RESOURCE_EXHAUSTED` | **Verified** |
| **Application HTTP Fallback Runs** | Live Uvicorn server receiving requests via `urllib.request` in `scripts/verify_task_010_live_http.py` | **Verified** |
| **Owner Manual Reproduction** | Manual owner CLI or terminal reproduction | **Pending** (ready for owner execution next week) |
