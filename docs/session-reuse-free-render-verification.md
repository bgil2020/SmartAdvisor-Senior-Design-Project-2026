# Session reuse and free Render verification

## Implemented local contract

- Browser memory holds at most 6 authenticated records, 120 KB per record, and 300 KB total.
- Identity includes record category, source ID, course, term, and section. Course descriptions and syllabi do not replace one another.
- The backend revalidates the existing record schema/content hash and an HMAC provenance signature. `SESSION_EVIDENCE_SIGNING_KEY` is backend-only; an unconfigured local process uses an ephemeral key.
- Matching evidence prevents acquisition even when retrieval finds no answer. Concurrent exact acquisition is deduplicated and the headed browser semaphore is one.
- Session reset aborts the active browser request and ignores responses from an older session epoch.
- Deterministic section retrieval and citations remain available with Gemini disabled.

## Free runtime

`Dockerfile` pins Playwright Python and the matching Microsoft Playwright Chromium image at 1.56.0, starts Xvfb, uses one Uvicorn worker, binds `$PORT`, and cleans up the app/display process group on termination. Headed mode must be explicitly selected; there is no headless-to-headed fallback.

Set `RENDER_STARTUP_BROWSER_SMOKE=true` only for a bounded startup verification deployment. The entrypoint refuses that mode unless syllabus acquisition is disabled and the conversational parser is deterministic. It renders a synthetic local page, proves timeout cancellation, closes Chromium, reports family-process peak RSS, and then starts the API. It exposes no debug or arbitrary-navigation endpoint.

Run `scripts/verify_container_512mb.ps1` on a machine with Docker to build and exercise the complete container under a hard 512 MB memory/swap limit. It records container-wide idle/peak memory, request duration, and Docker's OOM flag, then removes only its own named container.

## Deployment approval packet (not yet authorized)

Before any Render change, fill and present all of the following:

- Exact target: existing service name/ID or proposed isolated verification service.
- Branch and immutable commit SHA.
- Compute: Render Free, 512 MB, one API worker, no disk/database/worker/private service.
- Environment names changed (never secret values): `PORT`, `ACQUISITION_BROWSER_MODE`, `SYLLABUS_ACQUISITION_ENABLED`, `CONVERSATIONAL_PARSER_MODE`, `SESSION_EVIDENCE_SIGNING_KEY`, `RENDER_STARTUP_BROWSER_SMOKE`.
- Billing safeguards: current workspace plan, free instance availability, spend limit/payment exposure, and confirmation that no paid AI/browser/build dependency is enabled.
- Access protection and public URL behavior.
- Auto-deploy branch/filter behavior and whether the selected commit would deploy automatically.
- Verification: health, sanitized startup smoke, memory/OOM observation available from free-compatible logs/metrics, shutdown/restart, ordinary request, then one separately approved exact FAU mapping attempt.

## Current verification verdict

| Area | Result |
|---|---|
| Session reuse | Implemented; backend/unit and frontend tests passed locally |
| Local headed runtime | Not run; Docker/compatible Linux runtime unavailable on the current machine |
| 512 MB constrained container | Not run; Docker unavailable |
| Actual Render Free runtime | Not run; no controllable authenticated Render browser was available |
| Actual FAU access | Not run; gated on successful Render browser smoke and separate approval |
| AI free tier | Unconfirmed; Gemini remains optional and deterministic fallback works |
| Billing safeguards | Unconfirmed; no provisioning/deployment/configuration action taken |
| Frontend-to-backend demo | Partially tested by contracts/build; live browser acquisition demo not run |

This path is not yet “verified free.”
