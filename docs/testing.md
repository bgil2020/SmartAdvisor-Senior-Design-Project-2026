# SmartAdvisor Testing & Quality Assurance

This document details the test suites, execution commands, and manual verification procedures for SmartAdvisor.

---

## Automated Test Suites

### 1. Python Test Suite (Backend & Conversational)

Run all Python tests from the repository root:
```bash
pytest -v
```

#### Test Suite Breakdown:
- **`tests/test_api.py`:** Core FastAPI endpoints (`GET /`, `GET /courses`, `GET /sections`, `GET /alternatives`).
- **`tests/test_compatibility_api.py`:** `POST /compatibility` endpoint, CORS response headers, synthetic student profile evaluation.
- **`tests/test_conversational_api.py`:** `POST /conversation` endpoint, engine handoff, missing-context clarification, advisor escalation, inactive RAG boundary.
- **`tests/test_alternative_section_search.py`:** Section alternative search and non-conflicting replacement logic.
- **`tests/test_meeting_time_normalizer.py`:** Normalization of 12-hour/24-hour meeting times and day patterns.
- **`tests/test_overlap_detector.py`:** Day/time conflict detection across weekly calendar schedules.
- **`backend/tests/`:** Unit tests for conversational intent classification, regex entity extraction, and deterministic response policy.
- **`scripts/test_supabase_connection.py`:** Validates graceful handling of Supabase environment variables when unconfigured.

---

### 2. Frontend Test Suite

Run the frontend test suite from the `frontend/` directory:
```bash
cd frontend
npm test
```

#### Test Runner Details:
- Executes Node's native test runner (`node --experimental-strip-types --test tests/*.test.ts`).
- **`frontend/tests/test_override_evaluator.test.ts`:** Evaluates client-side logic for the Online Override Evaluator across military, medical, transportation, and other circumstances.
- **`frontend/tests/test_wiring_utils.test.ts`:** Validates schedule transformation utilities, 12-hour to 24-hour conversions, backend day mapping, CRN grouping, and real-section time conflict detection.
- **`frontend/tests/test_conversational_client.test.ts`:** Validates client conversational payload assembly, engine execution parsing, clarification prompts, and inactive RAG handling.

---

### 3. Frontend Lint and Build

Run linter and production build from `frontend/`:
```bash
cd frontend
npm run lint
npm run build
```
- **Lint:** ESLint flat config with TypeScript and React Hooks checks.
- **Build:** `tsc -b && vite build` verifying bundle compilation and strict TypeScript types.

---

## Manual Verification Checklist (Using Synthetic Inputs)

When performing release verification or smoke testing:

1. **Backend Health:**
   ```bash
   curl -s http://127.0.0.1:8000/
   ```
   *Expected:* JSON response with `"status": "ok"` and `"records_loaded": 913`.

2. **Course & Section Search:**
   ```bash
   curl -s "http://127.0.0.1:8000/sections?course=CAP%204773"
   ```
   *Expected:* Returns section record with CRN `19417`, instructor, days, and times.

3. **Alternative Search:**
   ```bash
   curl -s "http://127.0.0.1:8000/alternatives?crn=19417"
   ```
   *Expected:* Returns valid alternative section without schedule conflicts.

4. **Compatibility Engine:**
   ```bash
   curl -s -X POST http://127.0.0.1:8000/compatibility \
     -H "Content-Type: application/json" \
     -d '{"student_id":"Z24567901","proposed_courses":["COP4331","MAP3305"],"recent_difficulty":1,"satisfied_with_performance":"yes","work_hours":5.0,"preferred_max_credits":15.0,"recent_courses":["CDA4240C"]}'
   ```
   *Expected:* Returns `"success": true`, student name `"Evie Woods"`, and workload assessment.

5. **Conversational Scenarios (`POST /conversation`):**
   - **Engine Handoff:** Submit message `"Can I take COP 4331 and MAP 3305 together?"` with synthetic student context. Expect `response_code="ENGINE_EXECUTED"` and populated `engine_result`.
   - **Missing Context:** Submit message `"Can I take COP 4331?"` without student context. Expect `response_code="NEEDS_CLARIFICATION"` listing missing student workload fields.
   - **Advisor Escalation:** Submit message `"Can you approve my course override?"`. Expect `response_code="ADVISOR_ESCALATED"`.
   - **Inactive RAG Boundary:** Submit message `"What does the syllabus cover?"`. Expect `response_code="RAG_INACTIVE"` and `future_rag_candidate=true`.
