# SmartAdvisor Task 1 Integration and Task 2 Handoff

## Release boundary

This document describes the locally reviewed integration on `feature/syllabus-collector` after merging fetched `origin/main` (`0931116427646ea54853f8a1817cfc287b2809a8`). The exact runtime release commit is `2a36f5a7f41d3877e81580e1c33fe004e84ec6b7`. This is a local integration, not a deployment, free-tier verification, or production-readiness claim.

Persistent RAG publication remains available as historical prototype code from main, but the active MVP request path keeps normalized, signed evidence in bounded browser memory. It does not require an operational document store.

## Integrated capability map

| Capability | Frontend entry | Backend/handler | Integrated behavior |
|---|---|---|---|
| Compatibility | Compatibility form and conversational assistant | `POST /compatibility`; `/conversation` -> `evaluate_compatibility` | Uses the authoritative workbook evaluator and preserves advisor limitations. |
| Scheduling | Course/section selection, conflict calendar, alternatives dialog, conversation | `GET /courses`, `GET /sections`, `GET /alternatives`; conversation scheduling service | Uses the authoritative section catalog, overlap detector, and alternative search. |
| Override screening | Conversational handoff plus Online Course Override Evaluator | Client `evaluateOverride` | Conversation prefills/focuses the authoritative client evaluator; it never grants eligibility or approval. |
| RAG information | Conversational assistant source scope and session reset | `POST /conversation` -> session validation -> in-memory retriever -> provider adapter/fallback | Reuses signed exact-scope evidence, validates provider citation IDs, and does not refetch when a retained source lacks a requested detail. |

## Supported sources and acquisition

- Catalog category: `course_description`, restricted to the five exact URL mappings in `data/course_descriptions/sample-manifest.json`: `CAP4773`, `CDA4102`, `COP4331`, `EEL3111`, and `EGN4950C`.
- Syllabus category: `syllabus`, restricted to the exact course/term/section/document mappings in `data/syllabi/sample-manifest.json` (`CAP4773/202608/001`, `COP4331/202608/002`, and `EEL3111/202608/001`).
- Catalog acquisition performs one bounded request to the mapped official URL; it does not discover or accept arbitrary URLs. Syllabus acquisition performs one headed navigation to its exact mapping and never retries headless denial in headed mode or switches modes.
- Both adapters are disabled by default. Source HTML is parsed and identity/content validated before a signed normalized record is returned. Shells, challenges, errors, wrong identities, oversized responses, and incomplete content are rejected.
- Browser session bounds remain 6 records, 120,000 bytes per record, and 300,000 bytes total. `SESSION_EVIDENCE_SIGNING_KEY` must be a stable backend-only value of at least 32 bytes. Unsigned and tampered records are rejected.

## Reproducible local verification

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Push-Location frontend
npm ci
npm test
npm run lint
npm run build
Pop-Location
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\verify_local_session_ui.py
```

The browser verifier uses saved fixture evidence and mocks only the initial acquisition result. It makes no FAU or Gemini request. The RAG unit suite uses offline provider stubs for successful generation and forced provider failure.

## Container and Task 2 gate

Build and start the reviewed single-origin artifact:

```powershell
docker build -t smartadvisor-task2 .
docker run --rm --memory 512m --memory-swap 512m -p 8000:8000 `
  -e SESSION_EVIDENCE_SIGNING_KEY='<stable-random-secret>' `
  -e CONVERSATIONAL_PARSER_MODE=deterministic `
  -e RAG_GENERATION_MODE=fallback `
  -e CATALOG_ACQUISITION_ENABLED=false `
  -e SYLLABUS_ACQUISITION_ENABLED=false `
  smartadvisor-task2
```

For the synthetic headed smoke, use `scripts/verify_container_512mb.ps1`. The container starts Xvfb and one Uvicorn worker; the entrypoint traps exit/interrupt/termination and stops the app and Xvfb. The browser adapter closes its context and browser on success, error, and timeout. Do not remove browser sandbox flags or describe them as memory tuning.

Environment variable names:

- Required for session evidence: `SESSION_EVIDENCE_SIGNING_KEY`.
- API/runtime: `PORT`, `SMARTADVISOR_CORS_ORIGINS`, `SMARTADVISOR_SERVE_FRONTEND`.
- Parser/provider: `CONVERSATIONAL_PARSER_MODE`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_TIMEOUT_SECONDS`, `RAG_GENERATION_MODE`.
- Catalog acquisition: `CATALOG_ACQUISITION_ENABLED`, `CATALOG_ACQUISITION_TIMEOUT_SECONDS`, `CATALOG_ACQUISITION_MAX_BYTES`.
- Syllabus/browser: `SYLLABUS_ACQUISITION_ENABLED`, `ACQUISITION_BROWSER_MODE`, `ACQUISITION_TIMEOUT_SECONDS`, `RENDER_STARTUP_BROWSER_SMOKE`.

## Required Task 2 checks and stop conditions

Required access/approvals: Docker or equivalent Linux builder, an approved 512 MB runtime, read-only Render service/settings access, confirmation of tracked branch and auto-deploy behavior, an approved FAU live-source attempt, and provider account/no-cost/billing-safeguard confirmation. Suggested live candidates are the exact manifest entries above; test one approved mapping at a time.

Stop without deploying or continuing live acquisition if the image exceeds the memory limit/OOMs, Xvfb or Chromium children remain, the exact source returns denial/challenge/incomplete content, identity validation fails, the configured provider may incur unapproved cost, signing configuration is unstable, branch merge would auto-deploy without approval, or required logs expose source content/secrets. Roll back by stopping the candidate service and restoring the previously approved image/commit through the hosting platform's normal reviewed process.

Current local limitation: Docker is unavailable. The offline Windows headed smoke rendered and cleaned up successfully but observed a 526.6 MB peak, which is not a Linux 512 MB result and must not be treated as one. Render settings, free-tier eligibility, billing controls, live FAU access, and live Gemini behavior remain unverified Task 2 gates.
