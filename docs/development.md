# SmartAdvisor Development & Contributor Guide

This guide describes how to configure your local development environment, run the services, and follow the project conventions.

---

## Prerequisites

- **Python:** Python 3.11+ (verified with Python 3.11.5)
- **Node.js:** Node.js 22.13.0+ (verified with Node.js v22.19.0 and npm 10.9.3)
  > [!NOTE]
  > Node.js 22.13.0+ is required because the frontend test runner uses Node's native type stripping (`--experimental-strip-types`), and devDependencies require modern Node engine ranges.

---

## Local Setup

### 1. Clone & Python Environment

```bash
git clone https://github.com/bgil2020/SmartAdvisor-Senior-Design-Project-2026.git
cd SmartAdvisor-Senior-Design-Project-2026

# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate       # macOS / Linux
# or: .venv\Scripts\activate   # Windows

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Frontend Dependencies

```bash
cd frontend
npm ci
cd ..
```

---

## Running the Application

SmartAdvisor runs as a split frontend/backend application during local development. Run both in separate terminal sessions:

### Terminal 1: Backend API
```bash
source .venv/bin/activate  # if not already active
python -m uvicorn backend.api:app --reload --port 8000
```
- API Health Check: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- Interactive API Documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Terminal 2: Frontend UI
```bash
cd frontend
npm run dev
```
- Web Application: [http://localhost:5173/](http://localhost:5173/)

---

## Directory Organization & Conventions

```text
SmartAdvisor-Senior-Design-Project-2026/
├── frontend/                # Complete React 19 + TypeScript + Vite application
│   ├── src/                 # Active UI components, services, and utilities
│   ├── public/              # Static assets
│   ├── tests/               # Native TypeScript frontend unit tests
│   ├── index.html           # Single-page application entry HTML
│   ├── package.json         # Node scripts & dependencies
│   └── vite.config.ts       # Vite bundler configuration
├── backend/                 # Authoritative FastAPI services & compatibility engine
│   ├── api.py               # Main FastAPI entry point and routes
│   ├── compatibility_engine.py # Core compatibility evaluation engine
│   ├── compatibility_router.py # Compatibility REST router
│   ├── compatibility_data/  # Authoritative datasets for compatibility engine
│   ├── app/conversational/  # Deterministic conversational classifier & response policy
│   ├── docs/                # Conversational module specifications
│   └── tests/               # Conversational unit tests & dataset evaluation
├── data/                    # Active shared runtime datasets (FAU_Courses.xlsx)
├── tests/                   # Unified Python integration and API test suite
├── scripts/                 # Migration and administrative utility scripts
├── supabase/                # Database migrations and schema definitions
├── docs/                    # Modular architectural and contributor documentation
├── examples/legacy/         # Preserved historical prototypes and standalone workbooks
├── requirements.txt         # Python dependencies
└── pytest.ini               # Pytest test discovery configuration
```

### Conventions:
- **Never commit secrets:** The application runs completely offline using local Excel files. Do not commit `.env` files or API keys.
- **Keep application code clean:** Active features belong in `frontend/` or `backend/`. Historical prototypes belong in `examples/legacy/`.
- **Run tests before pushing:** Ensure both Python and frontend test suites pass before submitting changes.
