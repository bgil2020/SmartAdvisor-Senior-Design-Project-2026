# Home, Forms, and Shared Planning Chat UI Handoff

## Checkpoint boundary

- Repository/worktree: `D:\Projects\SmartAdvisor-Senior-Design-Project-2026`
- Branch: `integration/micen-updated-frontend`
- Base before this UI checkpoint: `a1d760ff88ce406d788944e74867bdbab152c316`
- Checkpoint: the local commit containing this note; resolve its exact immutable SHA with `git rev-parse HEAD` before beginning the next task.
- This is a local checkpoint only. It has not been pushed, merged, deployed, or used to change hosting or billing.

The following unrelated untracked files are deliberately excluded and must remain untouched:

- `docs/task_009_live_http_evidence.json`
- `scripts/verify_live_http_fallback.py`

## Completed UI functionality

- The polished Home screen remains the default entry and routes to `/forms` and `/chatbot`; direct loads and refreshes work.
- `/forms` and `/chatbot` use the shared `CoursePlanningWorkspace` for the real catalog, section selection, selected-section cards, multi-meeting calendar rendering, conflict indicators, asynchronous/TBA labeling, loading/error states, and add/remove behavior.
- `/chatbot` is a responsive 65/35 desktop workspace. At narrow widths the planning and chat panels stack.
- Selection state is owned by the application and remains consistent while navigating between Forms and Chatbot in the same browser session.
- Chat keeps a chronological user/assistant transcript, keeps citations with their response, snapshots selected CRN/course/section/term context per request, and sends supported structured context to the existing `/conversation` scheduling workflow.
- Clear chat cancels the active request, clears transcript plus signed evidence/source scope, rejects stale responses, preserves selected classes, and makes no automatic request.
- The existing compatibility form and truthfully labeled client-side override evaluator remain available on `/forms`.

Primary files:

- `frontend/src/App.tsx`
- `frontend/src/components/CoursePlanningWorkspace.tsx`
- `frontend/src/components/ConversationalAssistant.tsx`
- `frontend/src/components/WelcomeScreen.tsx`
- `frontend/src/services/api.ts`
- `frontend/src/utils/planningSelection.ts`
- `frontend/src/utils/conversationState.ts`
- `frontend/src/utils/viewRouting.ts`
- `frontend/src/index.css`
- `frontend/tests/test_planning_workspace.test.ts`
- `frontend/tests/test_view_routing.test.ts`
- `scripts/verify_local_session_ui.py`
- `docs/ui-verification/`

No backend contract change was needed. The existing request model already supports `sections`, `selected_sections`, and `term`; the frontend TypeScript contract now exposes those fields.

## Fresh verification at this checkpoint

- Frontend: `43` tests passed; ESLint passed; production TypeScript/Vite build passed (`28` modules transformed).
- Affected backend/API/scheduling suites: `69` tests passed with one existing Starlette/AnyIO deprecation warning.
- `git diff --check` passed.
- Offline local Chrome integration verifier passed against real Vite and FastAPI servers:
  - measured desktop split: `0.6500052787781389` planning / remaining chat;
  - direct `/forms` and `/chatbot` refreshes passed;
  - CAP 4773 section 002 (CRN `19416`) and MAP 3305 section 001 (CRN `16644`) remained consistent across pages;
  - the exact structured pair reached `/conversation` and returned `engine_executed` / `SCHEDULE_CONFLICT_FOUND`;
  - add/remove/re-add updated the calendar; four real meeting events rendered;
  - multiple exchanges, citations, follow-up evidence reuse, insufficient-evidence handling, clear-chat no-request behavior, request cancellation, and stale-response rejection passed;
  - narrow layout stacked successfully.

The citation/session portion used the approved offline COP 4331 syllabus fixture with acquisition test budgets set to zero. It does not establish live Gemini generation or live FAU acquisition. Screenshots are in `docs/ui-verification/`.

## Local startup

Backend, from the repository root:

```powershell
.\env\Scripts\python.exe -m uvicorn backend.api:app --reload --port 8000
```

Frontend, in another terminal:

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173/`, `http://localhost:5173/forms`, or `http://localhost:5173/chatbot`.

## Configuration variable names

Do not place values in handoff notes, chat, commits, screenshots, or logs.

- `CONVERSATIONAL_PARSER_MODE`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `GEMINI_TIMEOUT_SECONDS`
- `RAG_GENERATION_MODE`
- `SESSION_EVIDENCE_SIGNING_KEY`
- `SMARTADVISOR_CORS_ORIGINS`
- `VITE_API_URL`
- `CATALOG_ACQUISITION_ENABLED`
- `CATALOG_ACQUISITION_TIMEOUT_SECONDS`
- `CATALOG_ACQUISITION_MAX_BYTES`
- `SYLLABUS_ACQUISITION_ENABLED`
- `ACQUISITION_BROWSER_MODE`
- `ACQUISITION_TIMEOUT_SECONDS`

## Known limitations and next task

- The scheduling engine compares exactly two sections; more than two produces clarification rather than silently selecting a pair.
- Selection and transcript state are browser-memory only and reset on a full refresh.
- Override screening remains client-side because there is no override backend.
- Live Gemini answer generation and live FAU acquisition remain unverified.

Next task: verify bounded live Gemini answer generation through the newer `/chatbot` UI. Do not issue any provider request until the bounded test scope, account state, quota/cost safeguards, and explicit approval are confirmed. Live FAU acquisition is a separate unverified gate and must not be started as part of Gemini verification without separate explicit approval.
