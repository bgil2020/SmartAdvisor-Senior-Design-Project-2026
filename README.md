# SmartAdvisor

SmartAdvisor is an academic course-planning and advising decision-support system designed to help undergraduate engineering and computer science students evaluate course compatibility, detect schedule conflicts, find non-conflicting section alternatives, and screen online course override eligibility.

> [!IMPORTANT]
> **Advising Scope & Authority Boundary:**
> SmartAdvisor is a **decision-support prototype**, not an authoritative university registration system. It cannot officially approve course overrides, authorize policy exceptions, perform official graduation degree audits, or register students for classes. All recommendations are preliminary guidance. Official approvals require consultation with an authorized academic advisor or university registrar office.

---

## Capabilities & System Status

| Capability / Area | Status | Operational Details |
| :--- | :--- | :--- |
| **Course Catalog & Sections** | Integrated | File-backed via `data/FAU_Courses.xlsx`. Interactive search by department, course code, and term via `GET /courses` and `GET /sections`. |
| **Conflict & Alternative Search** | Integrated | Automatic day/time overlap detection and alternative section replacement via `GET /alternatives`. Interactive section swapping modal in the UI. |
| **Weekly Schedule Calendar** | Integrated | Visual calendar rendering real section meeting days and times, plus separate evening/unscheduled section panels. |
| **Course Compatibility Engine** | Integrated | Evaluates course combinations, credit load bounds, and workload difficulty against synthetic student profiles via `POST /compatibility`. |
| **Online Override Evaluator** | Client-Side Guidance | Interactive questionnaire screening student circumstances (military, medical, transportation, other). Runs pure browser-side logic; does not submit official overrides. |
| **Conversational Assistant** | Integrated (Deterministic) | Rule-based intent classification and entity extraction (`POST /conversation`). Automatically executes the Course Compatibility Engine when complete context is provided, requests missing workload fields, and escalates administrative requests to advisors. |
| **Data Runtime** | File-Backed | Operates entirely from local Excel workbooks. No cloud databases, external APIs, or network credentials are required. |
| **Supabase Cloud Database** | Prepared (Inactive) | Database schema and migration scripts exist in `supabase/` and `scripts/`. Inactive at runtime; adding credentials does not alter backend behavior. |
| **LLM & Vector RAG** | Planned Boundary | Informational queries are categorized with `future_rag_candidate=true` and safe `RAG_INACTIVE` guidance. No generative models or vector databases are connected. |
| **Session Persistence** | In-Memory (Client) | Active schedule and chat history are held in React state; refreshing the browser resets the session. |

---
##Recent Development Updates
--

## Requirements

- **Python:** Python 3.11+ (verified on **Python 3.11.5**)
- **Node.js:** Node.js 22.13.0+ (verified on **Node.js v22.19.0** and **npm 10.9.3**)  
  *Note:* Node.js 22.13.0+ is required because the frontend test runner uses Node's native type stripping (`--experimental-strip-types`) and dependencies require modern Node engine ranges.

---

## Clean-Clone Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/bgil2020/SmartAdvisor-Senior-Design-Project-2026.git
cd SmartAdvisor-Senior-Design-Project-2026
```

### 2. Configure Python Virtual Environment
```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate

# Install Python backend dependencies
pip install -r requirements.txt
```

### 3. Install Frontend Dependencies
```bash
cd frontend
npm ci
cd ..
```

### 4. Start Services (Separate Terminals)

**Terminal 1 — Backend API:**
```bash
source .venv/bin/activate  # macOS / Linux (or .venv\Scripts\activate on Windows)
python -m uvicorn backend.api:app --reload --port 8000
```
- API Status: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- Interactive API Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

**Terminal 2 — Frontend Application:**
```bash
cd frontend
npm run dev
```
- Open application in browser: [http://localhost:5173/](http://localhost:5173/)

---

## Testing & Quality Assurance

Run verification commands from a clean checkout:

### Python Test Suite (All Backend & Conversational Tests)
From the repository root:
```bash
pytest -v
```
*(Verified checkpoint: 89 passed across API, compatibility, conversational, and database test suites)*

### Frontend Test Suite
From the `frontend/` directory:
```bash
cd frontend
npm test
```
*(Verified checkpoint: 32 tests passed across 11 suites using Node native test runner)*

### Frontend Lint and Build
```bash
cd frontend
npm run lint    # ESLint TypeScript and React Hooks check (0 errors)
npm run build   # TypeScript type-check and Vite production bundle build
```

For detailed test suite breakdowns and manual verification checklists with synthetic inputs, see [docs/testing.md](docs/testing.md).

---

## Repository Structure

```text
SmartAdvisor-Senior-Design-Project-2026/
├── frontend/                     # Active React 19 + TypeScript + Vite web application
│   ├── src/                      # UI components, services, and utilities
│   ├── public/                   # Static web assets
│   ├── tests/                    # Frontend unit test suites (Node test runner)
│   ├── index.html                # Vite HTML entry point
│   ├── package.json              # Frontend scripts and dependencies
│   ├── vite.config.ts            # Vite bundler configuration
│   └── tsconfig*.json            # TypeScript compiler configuration
├── backend/                      # Active FastAPI application and domain services
│   ├── api.py                    # Main FastAPI application entry point
│   ├── section_retriever.py      # Course and section data retrieval
│   ├── overlap_detector.py       # Meeting time conflict detection
│   ├── alternative_section_search.py # Section alternative search
│   ├── compatibility_engine.py   # Course workload compatibility evaluation
│   ├── compatibility_router.py   # FastAPI router for POST /compatibility
│   ├── compatibility_data/       # Authoritative datasets for compatibility engine
│   ├── app/conversational/       # Deterministic conversational assistant layer
│   │   ├── intent_classifier.py  # Rule-based intent classifier
│   │   ├── entity_extractor.py   # Regex entity extractor & normalizer
│   │   └── response_policy.py    # Routing policy & engine handoff
│   ├── docs/                     # Conversational component specifications
│   └── tests/                    # Conversational unit tests & dataset evaluation
├── data/                         # Active runtime datasets
│   ├── FAU_Courses.xlsx          # Authoritative course & section catalog
│   └── data_dictionary.md        # Dataset field schema and definitions
├── tests/                        # Root Python API and integration test suites
│   ├── test_api.py               # Core FastAPI endpoint tests
│   ├── test_compatibility_api.py # Compatibility API tests
│   └── test_conversational_api.py# Conversational API and handoff tests
├── scripts/                      # Database utilities and migration scripts
├── supabase/                     # Supabase schema definitions and setup guides
├── docs/                         # Detailed architecture, API, development, and test docs
│   ├── README.md                 # Documentation index
│   ├── architecture.md           # System architecture and component boundaries
│   ├── api.md                    # REST API endpoint reference and payloads
│   ├── development.md            # Contributor guide and environment setup
│   └── testing.md                # Testing matrix and manual smoke checklist
├── examples/legacy/              # Preserved historical prototypes and standalone workbooks
│   ├── course_compatibility_engine.py
│   ├── smartadvisor.py
│   ├── smartadvisor_personalized_prototype_v5.py
│   ├── test_compatability_api.py
│   └── README.md                 # Legacy documentation and execution instructions
├── requirements.txt              # Backend Python dependencies
├── pytest.ini                    # Root Pytest discovery configuration
└── .env.example                  # Optional environment configuration template
```

---

## Component & Contributor Map

| Component | Contributor(s) | Current Path | Runtime Entry Point / Status |
| :--- | :--- | :--- | :--- |
| **Backend API & Scheduling Services** | Jeffrey Huang (Cloud2856) | `backend/api.py`<br>`backend/section_retriever.py`<br>`backend/overlap_detector.py`<br>`backend/alternative_section_search.py` | `python -m uvicorn backend.api:app`<br>Active runtime service reading `data/FAU_Courses.xlsx`. |
| **Course Compatibility Engine** | Batsheva Gil (bgil2020) | `backend/compatibility_engine.py`<br>`backend/compatibility_router.py`<br>`backend/compatibility_data/` | `POST /compatibility`<br>Active service reading `backend/compatibility_data/`. |
| **Frontend Web Application** | Micen Desjardins (micenD2003) | `frontend/src/App.tsx`<br>`frontend/src/components/ScheduleCalendar.tsx`<br>`frontend/src/services/api.ts` | `npm run dev` (in `frontend/`)<br>Active React UI connected to backend. |
| **Online Override Evaluator** | Batsheva Gil (bgil2020) | `frontend/src/components/OnlineOverrideEvaluator.tsx`<br>`frontend/src/utils/overrideEvaluator.ts` | Embedded in `frontend/src/App.tsx`<br>Active client-side screening form. |
| **Conversational Layer & Integration** | Fareed Uddin (fareedom1) | `backend/app/conversational/`<br>`backend/tests/`<br>`tests/test_conversational_api.py` | `POST /conversation`<br>Deterministic intent routing, entity extraction, and compatibility engine handoff. |
| **Historical Prototypes** | Team | `examples/legacy/` | Standalone prototypes preserved for reference and historical provenance. |

---

## Configuration & Data Integrity

1. **Supplied Workbooks:**
   - Active runtime workbooks (`data/FAU_Courses.xlsx` and `backend/compatibility_data/`) are tracked in the repository and ready for immediate local execution.
2. **Local API Configuration:**
   - The frontend connects to `http://127.0.0.1:8000` by default. To point to an alternate backend address, define `VITE_API_URL` in `frontend/.env`.
3. **No External Credentials Required:**
   - SmartAdvisor operates 100% offline in file-backed mode. No database credentials, API keys, or cloud accounts are needed.
4. **Secret Handling Boundaries:**
   - Never commit secrets, service-role keys, or student data to Git. Keep `.env` files untracked. All profile data used in testing (`Synthetic Profiles.xlsx`) is strictly synthetic.

---

## Documentation Links

For deeper technical information, consult the project guides:
- [Documentation Index](docs/README.md)
- [Architecture & Boundaries](docs/architecture.md)
- [API Specification](docs/api.md)
- [Development & Contributor Guide](docs/development.md)
- [Testing & Quality Assurance](docs/testing.md)
- [Legacy Prototypes Guide](examples/legacy/README.md)
