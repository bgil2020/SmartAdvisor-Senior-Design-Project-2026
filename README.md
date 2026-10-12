# SmartAdvisor

SmartAdvisor is an academic course-planning and advising decision-support system designed to assist undergraduate students in navigating course compatibility, detecting scheduling conflicts, evaluating section alternatives, and screening online course override eligibility.

> **Important Advisor-Authority & Scope Disclaimer:**  
> SmartAdvisor is a **decision-support prototype**, not an authoritative university system. It does not possess academic authority, cannot officially approve overrides, and cannot register students for courses. All override recommendations are preliminary planning guidance only; official override submission, policy exceptions, degree audits, and final approvals require review by an authorized academic advisor or university office.

---

## Current Implementation Status

| Feature / Component | Status Category | Current Delivery & Operational Mode |
| ------------------- | --------------- | ----------------------------------- |
| **Course Catalog & Section Retrieval** | Integrated (Backend API & Frontend) | File-backed via `data/FAU_Courses.xlsx`; exposed via `GET /courses` and `GET /sections`; interactive course selector & section browser in UI. |
| **Scheduling Conflict Detection** | Implemented (Backend API & Frontend) | Backend overlap detector (`overlap_detector.py`) and visual frontend calendar conflict highlighter (`getConflictingSectionIds`). |
| **Alternative Section Search** | Integrated (Backend API & Frontend) | File-backed non-conflicting replacement via `GET /alternatives`; interactive browser modal with section swapping. |
| **Course Compatibility Engine** | Integrated (Backend API & Frontend) | Evaluates workload & risk via `POST /compatibility`; interactive browser panel with synthetic profile selection (`Synthetic Profiles.xlsx`). |
| **Weekly Schedule Calendar** | Integrated (Browser UI) | Visual calendar layout rendering proposed schedule and selected FAU section meetings, separate unscheduled/evening panel, and clearly labeled simulated mock demonstration toggle. |
| **Online Override Evaluator** | Implemented (Browser UI) | Browser-side preliminary guidance questionnaire (`src/components/OnlineOverrideEvaluator.tsx`). No official override submission or university workflow connection. |
| **Conversational Intent Classifier** | Implemented (Python Module) | Deterministic keyword/regex classification across 6 canonical intents (`backend/app/conversational/intent_classifier.py`). |
| **Conversational Entity Extractor** | Implemented (Python Module) | Rule-based extraction & normalization of courses, sections, times, days, and modalities (`backend/app/conversational/entity_extractor.py`). |
| **Conversational Response Policy** | Implemented (Python Module) | Deterministic routing decision & safety policy (`backend/app/conversational/response_policy.py`). **Does not yet dispatch backend engines.** |
| **Supabase Cloud Database** | Prepared / File-Backed Runtime Retained | Schema and seed/test scripts exist in `supabase/` and `scripts/`. Runtime APIs (`backend/api.py`) are strictly file-backed. Adding credentials does not alter runtime behavior. |
| **LLM Adapter & RAG Retrieval** | Planned / Separate Milestone | Informational queries are safely flagged as inactive candidates (`future_rag_candidate`). No live LLM or vector RAG is active. |

---

## Component Map & Team Attribution

| Component | Contributor / Owner | Current Path(s) | Public Entry Point / Runtime Usage | Status & Connectivity |
| --------- | ------------------- | --------------- | ---------------------------------- | --------------------- |
| **Backend API & Scheduling Services** | Cloud2856 (Jeffrey Huang) | `backend/api.py`<br>`backend/section_retriever.py`<br>`backend/overlap_detector.py`<br>`backend/alternative_section_search.py`<br>`backend/meeting_time_normalizer.py`<br>`backend/result_formatter.py` | `uvicorn backend.api:app`<br>Endpoints: `GET /`, `GET /courses`, `GET /sections`, `GET /alternatives` | Implemented; reads `data/FAU_Courses.xlsx`. |
| **Course Compatibility Engine** | bgil2020 (Batsheva Gil) | `backend/compatibility_engine.py`<br>`backend/compatibility_router.py`<br>`backend/compatibility_data/` | `POST /compatibility`<br>(Standalone script: `course_compatibility_engine.py`) | Implemented; integrated into FastAPI router; reads compatibility Excel datasets. |
| **Frontend Web Application & API Wiring** | micenD2003 (Micen Desjardins) / fareedom1 | `src/App.tsx`<br>`src/services/api.ts`<br>`src/components/ScheduleCalendar.tsx`<br>`src/utils/scheduleUtils.ts` | `npm run dev`<br>URL: `http://localhost:5173/` | Wired to backend REST endpoints; supports live course search, calendar display, section alternatives, and compatibility evaluations. |
| **Online Override Evaluator (UI Integration)** | bgil2020 (Batsheva Gil) / fareedom1 | `src/components/OnlineOverrideEvaluator.tsx`<br>`src/utils/overrideEvaluator.ts`<br>`src/types/override.ts` | Embedded in `src/App.tsx` | Implemented client-side; evaluates military, medical, transportation, other circumstances. |
| **Deterministic Conversational Baseline** | fareedom1 (Fareed Uddin) | `backend/app/conversational/intent_classifier.py`<br>`backend/app/conversational/entity_extractor.py`<br>`backend/app/conversational/response_policy.py`<br>`backend/tests/` | Python function:<br>`build_conversation_response(message)` | Implemented offline Python module; generates structured routing decisions; does not dispatch engines. |
| **Integration & Test Suites** | fareedom1 / Team | `tests/`<br>`backend/tests/`<br>`tests/frontend/`<br>`pytest.ini` | `pytest -v`<br>`npm test` | Unified test discovery across all backend, conversational, and frontend suites. |

---

## Repository Structure

```text
SmartAdvisor-Senior-Design-Project-2026/
├── backend/
│   ├── api.py                             # Authoritative FastAPI entry point
│   ├── compatibility_engine.py            # Authoritative runtime compatibility engine
│   ├── compatibility_router.py            # FastAPI router for POST /compatibility
│   ├── alternative_section_search.py      # Replacement section finder
│   ├── overlap_detector.py                # Time overlap conflict checker
│   ├── section_retriever.py               # File-backed course/section retrieval
│   ├── meeting_time_normalizer.py         # Meeting day/time string normalization
│   ├── result_formatter.py                # Response formatting utilities
│   ├── compatibility_data/                # Authoritative data files used by compatibility engine
│   │   ├── Course Combinations.xlsx
│   │   ├── Final_FAU_CS_CE_EE_Undergraduate_Courses_Revised (1) (2).xlsx
│   │   └── Synthetic Profiles.xlsx
│   ├── app/
│   │   └── conversational/                # Authoritative conversational baseline
│   │       ├── intent_classifier.py       # Rule-based intent classifier (6 canonical intents)
│   │       ├── entity_extractor.py        # Regex entity extractor & normalizer
│   │       └── response_policy.py         # Deterministic routing & safety policy
│   ├── docs/                              # Conversational documentation
│   │   ├── conversational_intent_classifier.md
│   │   └── conversational_response_policy.md
│   └── tests/                             # Conversational test suite & dataset fixture
│       ├── fixtures/conversational_prompt_dataset.json
│       ├── test_dataset_evaluation.py
│       ├── test_entity_extractor.py
│       ├── test_intent_classifier.py
│       └── test_response_policy.py
├── data/
│   ├── FAU_Courses.xlsx                   # Authoritative course workbook for backend API
│   ├── data_dictionary.md                 # Dataset field dictionary
│   └── sample_records.json                # Synthetic course records sample
├── src/                                   # React + TypeScript frontend
│   ├── App.tsx                            # Main application layout
│   ├── components/
│   │   ├── ScheduleCalendar.tsx           # Weekly calendar view (renders demo schedule)
│   │   ├── OnlineOverrideEvaluator.tsx    # Interactive override guidance form
│   │   ├── CourseSelectionForm.tsx        # Preserved initial selection form component
│   │   └── OnlineOverrideForm.tsx         # Preserved initial override form component
│   ├── utils/
│   │   ├── overrideEvaluator.ts           # Pure business logic for override evaluation
│   │   └── scheduleUtils.ts               # Calendar layout & time arithmetic helpers
│   └── types/
│       ├── override.ts                    # TypeScript types for override evaluation
│       └── schedule.ts                    # TypeScript types for schedule display
├── tests/                                 # Root backend and frontend test suites
│   ├── test_api.py                        # FastAPI core endpoint tests
│   ├── test_compatibility_api.py          # Compatibility endpoint & CORS regression tests
│   ├── test_alternative_section_search.py # Section alternative tests
│   ├── test_meeting_time_normalizer.py    # Time normalizer tests
│   ├── test_overlap_detector.py           # Schedule conflict detector tests
│   └── frontend/
│       └── test_override_evaluator.test.ts# Node test runner suite for frontend logic
├── scripts/                               # Data import & database connection utilities
│   ├── import_course.py
│   ├── test_supabase_connection.py
│   └── upload_to_supabase.py
├── supabase/                              # Database migration & setup reference
│   ├── SETUP.md
│   └── migrations/20261009_initial_schema.sql
├── pytest.ini                             # Pytest discovery configuration
├── package.json                           # Frontend scripts & dependencies
├── requirements.txt                       # Backend Python dependencies
├── smartadvisor_conversational_prompt_dataset_draft.md # Conversational prompt dataset reference
│
│   # --- Preserved Prototype / Standalone Reference Files (Not deleted) ---
├── course_compatibility_engine.py         # Batsheva's standalone compatibility script
├── smartadvisor.py                        # Jeffrey's standalone backend prototype
├── smartadvisor_personalized_prototype_v5.py # Historical prototype
├── Course Combinations.xlsx               # Root-level prototype workbook copy
├── Synthetic Profiles.xlsx                # Root-level prototype workbook copy
└── Final_FAU_CS_CE_EE_Undergraduate_Courses_Revised(Sheet1).xlsx # Root-level prototype copy
```

---

## Setup and Execution

### Prerequisites & Verified Environments
- **Python:** Python 3.11+ (verified on **Python 3.11.5**)
- **Node.js:** Node.js 22.13.0+ (verified on **Node.js v22.19.0** and **npm 10.9.3**)  
  *Note on Node compatibility:* Both the dependency tree and the test runner establish this requirement: ESLint 10 devDependencies (such as `@eslint/config-array`) specify `^20.19.0 || ^22.13.0 || >=24`, and the native TypeScript test runner (`npm test`) relies on Node's `--experimental-strip-types` flag (introduced in Node 22.6.0). Earlier versions (including Node 18 and pre-22.13 Node 22 releases) are incompatible.

---

### Backend Setup

1. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # macOS/Linux
   # or: .venv\Scripts\activate  # Windows
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the FastAPI backend server:**
   ```bash
   python -m uvicorn backend.api:app --reload --port 8000
   ```

4. **Verify backend health & interactive Swagger docs:**
   - Status endpoint: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
   - Swagger / OpenAPI documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

### Frontend Setup

1. **Install Node packages:**
   ```bash
   npm ci
   ```

2. **Start the Vite development server:**
   ```bash
   npm run dev
   ```
   Open your browser to [http://localhost:5173/](http://localhost:5173/).

---

### Running Frontend and Backend Simultaneously

To run both the backend and frontend simultaneously, use **separate terminal windows**:
- **Terminal 1 (Backend API):** `python -m uvicorn backend.api:app --reload --port 8000`
- **Terminal 2 (Frontend UI):** `npm run dev`

Open your browser to [http://localhost:5173/](http://localhost:5173/).

> **Frontend-Backend Integration:** The frontend API client (`src/services/api.ts`) communicates directly with the backend API (`http://127.0.0.1:8000`, configurable via `VITE_API_URL`). The frontend automatically retrieves real courses from `GET /courses`, queries sections via `GET /sections?course=...`, requests non-conflicting alternatives via `GET /alternatives?crn=...`, and evaluates course workloads via `POST /compatibility`.

---

## Testing

All test commands are reproducible from a clean checkout.

### 1. Unified Python Test Suite (Backend & Conversational)
Run the root test command:
```bash
pytest -v
# or: python -m pytest -v
```
*Current Checkpoint Result:* **89 passed, 1 warning** (~1.5s)  
- 35 backend tests in `tests/` (course API, compatibility API, alternatives, time normalizer, overlap detector)
- 1 database script test in `scripts/test_supabase_connection.py`
- 43 conversational baseline tests in `backend/tests/` (dataset evaluation, entity extractor, intent classifier, response policy)
- 10 conversational API tests in `tests/test_conversational_api.py` (engine execution handoff, missing context, escalation, RAG boundary, validation)

To run specific test suites individually:
```bash
# Run only backend API tests:
pytest -v tests/

# Run only conversational tests:
pytest -v backend/tests/

# Run the labeled prompt dataset evaluation report:
python -m unittest backend/tests/test_dataset_evaluation.py
```

### 2. Frontend Unit Tests
```bash
npm test
```
*Current Checkpoint Result:* **26 passed across 8 suites** (~130ms)  
- Evaluates online override screening rules (military, medical, transportation, other circumstances).
- Evaluates schedule calendar utility functions (minute conversion, layout positioning, conflict identification).
- Evaluates frontend-backend wiring utilities (`parse12HourTo24Hour`, `parseBackendDays`, `mapBackendSectionToCourseSection`, in-grid/asynchronous mapping, and real section time overlap detection).
- Evaluates conversational client payload structure, missing context handling, and response states (`engine_executed`, `clarification`, `escalation`, `rag_inactive`).

### 3. Frontend Linter
```bash
npm run lint
```
*Current Checkpoint Result:* Clean (0 errors, 0 warnings).

### 4. Frontend Production Build
```bash
npm run build
```
*Current Checkpoint Result:* Compiles cleanly with TypeScript (`tsc -b && vite build`).

---

## API & Conversational Interfaces

### 1. REST API Endpoints (`backend/api.py`)

| Method | Endpoint | Description | Query / Body Parameters |
| ------ | -------- | ----------- | ----------------------- |
| `GET` | `/` | Application status & loaded record count | None |
| `GET` | `/courses` | Search courses from FAU dataset | `term` (optional), `department` (optional, e.g. `COP`), `modality` (optional) |
| `GET` | `/sections` | Retrieve course sections with optional filters | `course` (optional, e.g. `CAP 4773`), `crn` (optional, e.g. `19417`), `term` (optional), `modality` (optional) |
| `GET` | `/alternatives` | Search non-conflicting replacement sections | `crn` (required, e.g. `19417`), `selected_crns` (optional comma-delimited) |
| `POST` | `/compatibility` | Evaluate compatibility of course combination | JSON body: `student_id`, `proposed_courses`, `recent_difficulty`, `satisfied_with_performance`, `work_hours`, `preferred_max_credits`, `recent_courses` |
| `POST` | `/conversation` | Conversational assistant with compatibility engine execution | JSON body: `message` (required, 1-500 chars), optional synthetic student context (`student_id`, `recent_difficulty`, `satisfied_with_performance`, `work_hours`, `preferred_max_credits`, `recent_courses`) |

#### Synthetic Compatibility Payload Example
```json
{
  "student_id": "Z24567901",
  "proposed_courses": ["COP4331", "MAP3305", "CDA4630"],
  "recent_difficulty": 1,
  "satisfied_with_performance": "yes",
  "work_hours": 5.0,
  "preferred_max_credits": 15.0,
  "recent_courses": ["CDA4240C", "CDA4102", "MAC2313"]
}
```

---

### 2. Conversational API & Engine Handoff (`POST /conversation`)

The conversational layer connects natural-language student queries directly to backend decision support via `POST /conversation`:
- **Deterministic Intent & Entity Extraction:** Uses rule-based regex patterns for course codes, section identifiers, time ranges, and modalities without relying on ungrounded generative models.
- **Course Compatibility Engine Execution:** When a compatibility query is recognized and complete student workload context is attached, the backend directly executes `evaluate_compatibility(...)` and returns real risk scores, credit totals, recommendations, and warnings.
- **Clarification & Missing Context:** If required student workload context is omitted, the assistant provides actionable guidance explaining which fields are missing and retains the student's prompt.
- **Advisor Escalation:** Requests regarding official university authority (overrides, registration, graduation) are routed to advisor escalation with clear disclaimers.
- **Inactive RAG Boundary:** Informational queries (e.g. course topic overviews, prerequisites) are flagged as inactive RAG candidates (`future_rag_candidate`), keeping a strict boundary between the current deterministic prototype and future vector-retrieval features.

#### Conversational Request Example:
```json
{
  "message": "Can I take COP 4331 and MAP 3305 together?",
  "student_id": "Z24567901",
  "recent_difficulty": 1,
  "satisfied_with_performance": "yes",
  "work_hours": 5.0
}
```

#### Standardized Response Schema:
```json
{
  "raw_message": "Can I take COP 3330 and CEN 4010 together?",
  "disposition": "route_core_engine",
  "target_handler": "course_compatibility_engine",
  "intent": "course_compatibility_check",
  "entities": {
    "course_codes": ["COP3330", "CEN4010"],
    "section_identifiers": [],
    "schedule_constraints": { ... },
    "modality_preference": null,
    "missing_fields": [],
    "validation_errors": []
  },
  "needs_clarification": false,
  "missing_fields": [],
  "validation_errors": [],
  "response_code": "CORE_REQUEST_READY",
  "response_text": "Your request is ready to be checked for course compatibility.",
  "safe_to_route": true,
  "future_rag_candidate": false,
  "reason": null
}
```

#### Routing Decisions vs. Engine Execution
> **Critical Architectural Distinction:**  
> A response with `disposition="route_core_engine"`, `target_handler="course_compatibility_engine"`, or `safe_to_route=true` represents an **analyzed routing decision**, **not proof that a backend engine was dispatched**.  
> The conversational layer does not automatically trigger backend calculation.  
> Furthermore, executing the Course Compatibility Engine requires rich student context (such as `student_id`, recent difficulty rating, work hours, and preferred credit limits). The conversational layer extracts course codes from student prompts, but does not invent synthetic student profiles or default context. Bridging conversational routing to actual engine execution will occur in a dedicated wiring milestone.

---

## Configuration, Data, and Privacy

1. **Supplied Data Files vs. Database Runtime:**
   - **File-Backed Runtime:** All active application backend endpoints (`/courses`, `/sections`, `/alternatives`, `/compatibility`) read strictly from local Excel files (`data/FAU_Courses.xlsx` and `backend/compatibility_data/`).
   - **Supabase Role & Status:** Supabase schema definitions exist in `supabase/migrations/20261009_initial_schema.sql` (defining `courses`, `sections`, `risk_rules`, `student_profiles`), and upload/test scripts exist in `scripts/test_supabase_connection.py` and `scripts/upload_to_supabase.py`. However, zero application runtime code references Supabase, and adding credentials to `.env` does not alter API runtime behavior. For this wiring milestone, file-backed runtime is intentionally retained.
   - Any future database migration would require explicit team coordination, backend DAO/retriever implementation, and Supabase RLS policy configuration.

2. **Secrets & Frontend Configuration:**
   - The file-backed runtime operates **entirely offline** without database credentials, third-party API keys, or cloud access.
   - Frontend API base URL is configured via `VITE_API_URL` (defaults to `http://127.0.0.1:8000`).
   - `.env.example` provides optional configuration for host/port and Supabase connection placeholders. **Never commit actual database keys, service-role tokens, or secrets to version control, and never expose service-role credentials to frontend bundles.**

3. **Student Privacy Boundaries:**
   - No real student records or FERPA-protected identifiable information are stored in this repository.
   - All profile data in `Synthetic Profiles.xlsx` and testing suites are synthetic test artifacts.
   - The frontend Course Compatibility screener provides selection only among approved synthetic student profiles.

4. **Advising Policy Review Status:**
   - Override evaluation rules, category thresholds, and conversational guidance text reflect senior-design prototype logic and are subject to ongoing faculty and academic advisor review.

---

## Integration History & Roadmap

### Milestones Completed
- **PR #1 (Jeffrey Huang):** Integrated backend foundation, file-backed course and section retrieval, overlap conflict detection, alternative section search, and Supabase seed scripts.
- **PR #2 (Batsheva Gil):** Integrated Course Compatibility Engine, compatibility dataset fixtures, `/compatibility` API endpoint, and automated API regression tests.
- **PR #3 (Micen Desjardins & Batsheva Gil):** Integrated React + TypeScript frontend, Schedule Calendar layout, Online Override Evaluator component, unit tests, and ESLint configuration.
- **PR #4 (Fareed Uddin):** Consolidated deterministic conversational baseline (intent classifier, entity extractor, response policy), unified root test discovery (`pytest.ini`), synchronized dependencies and ignore rules, and delivered comprehensive project documentation.
- **Frontend-to-Backend Wiring Milestone (Current):** Connected the React dashboard directly to live FastAPI backend endpoints (`GET /courses`, `GET /sections?course=...`, `GET /alternatives?crn=...`, and `POST /compatibility`), preserving mock calendar data strictly behind an explicit toggle and maintaining browser-side override screening.

*Historical reference branches (`feature/conversational-intent-classifier`, `feature/course-compatibility`, `feature/override-main-integration`, `jeffrey-backend`) are preserved in the repository history for provenance and reference.*

### Next Milestones
1. **Conversational Engine Handoff:** Bridge conversational routing policies (`safe_to_route=true`) to backend engine endpoints with interactive UI presentation.
2. **LLM Structured Parser Integration:** Introduce an LLM-assisted semantic parser with deterministic rule-based fallback for complex, ambiguous, or multi-intent student queries.
3. **Database Migration (Optional/Future):** Implement Supabase backend data adapters if team approval is granted to transition from file-backed workbooks to cloud database persistence.