# Release, Docker, and hosted-routing handoff

## Release boundary

- Published main remains `0fca051c6b43108a8fc6d33a8566b26b19893c4f`.
- Local acquisition/reuse checkpoint: `f9a79fb33c51805dc57fb9861bb297f1332d6ac9`.
- Local combined-harness checkpoint: `bceb2451a3e39542ce9ea20504da3e7b7bb4673c`.
- The combined live workflow has **not** passed. Its first turn acquired the
  exact CAP4773 source and accepted one Gemini answer, but the support gate
  failed and no second turn ran.
- No commits after published main have been pushed, merged, or deployed.

Later local checkpoints remain distinct:

- `c7b241544a46498f6a99fa508d279ca96085b84c`: passed single-turn live grading
  diagnostic using fresh CAP4773 acquisition and one Gemini call.
- `7a932fc04cd2d5883848a5d33ea1f03c95c8b2ae`: shared production grading
  safeguard; offline verification only.

The live two-turn acquisition + Gemini + follow-up evidence-reuse workflow is
still unverified and must not be inferred from the single-turn pass.

Before release, checkpoint the offline numeric-checker correction, reconcile it
through the normal feature-branch/PR workflow, and rerun all backend/frontend
checks. A new combined live test requires separate approval.

## Current Docker verification

The root `Dockerfile` builds the Vite artifact, uses the Playwright Python
1.56.0 Noble image, starts Xvfb, serves one Uvicorn worker on `$PORT`, and sets
`SMARTADVISOR_SERVE_FRONTEND=true`. The entrypoint cleans up the API and Xvfb
process group. `scripts/verify_container_512mb.ps1` is the bounded 512 MiB
container check.

On 2026-11-20, Docker CLI `29.9.3` was installed, but the Docker Desktop Linux
engine pipe was absent. No image build or constrained-container run was
possible. Consequently Linux/Playwright compatibility, 512 MiB peak usage,
OOM status, single-container SPA refreshes, and container cleanup remain
unverified on the current tree.

The checked-in `infra/render.yaml` uses Render's Python runtime with
`pip install -r requirements.txt` and a plain Uvicorn start command. It does
not select the root Dockerfile or configure Xvfb/Playwright acquisition.
Applied Render dashboard settings must be inspected; repository defaults are
not proof of the deployed runtime.

## Known hosted fixes to investigate

1. **Vercel SPA routing:** no tracked `vercel.json` supplies an SPA fallback.
   Direct `/forms` and `/chatbot` refreshes therefore require a Vercel rewrite
   to the built `index.html`, while preserving static assets.
2. **Frontend API target:** `frontend/src/services/api.ts` defaults
   `VITE_API_URL` to an empty string, which means same-origin requests. The
   Vercel workflow performs `vercel pull` and `vercel deploy`, but the applied
   production build variable is not established by repository files. Verify
   that Vercel's production `VITE_API_URL` targets the intended Render API, or
   add a reviewed proxy architecture; do not assume same-origin works across
   the two hosts.
3. **Exact-origin CORS:** Render must apply `SMARTADVISOR_CORS_ORIGINS` with the
   exact production Vercel origin. Add preview origins only when explicitly
   required and reviewed. The backend default allows localhost only.
4. **Runtime alignment:** decide whether Render should remain Python-runtime
   API-only or intentionally use the Docker image for headed acquisition.
   Changing that runtime can trigger deployment and must follow the deployment,
   cost, memory, and live-source approval gates.

## Next offline sequence

1. Start Docker Desktop and run `scripts/verify_container_512mb.ps1` without
   enabling live acquisition or Gemini.
2. Add and test the Vercel SPA rewrite locally/build-time.
3. Verify the non-secret applied variable names and exact origins in the Vercel
   and Render dashboards; never copy values or credentials into evidence.
4. Validate Home, `/forms`, and `/chatbot` direct loads plus backend health,
   catalog GET, and exact-origin CORS using read-only requests.
5. Publish only after the reconciled tree, CI, deployment consequences, and
   required approvals are known.

## Exact approvals still required

No item below is authorized by this handoff:

1. **Docker verification approval:** start the Docker Desktop Linux engine and
   allow the bounded `scripts/verify_container_512mb.ps1` build/run, including
   registry downloads, one disposable local container, hard 512 MiB memory and
   swap limits, synthetic startup smoke, and automatic removal.
2. **Hosted configuration inspection:** authenticated read-only access to the
   applied Vercel production variables/project routing and Render service
   runtime, branch, environment-variable names, plan, and auto-deploy state.
3. **Offline hosting-fix implementation:** add and test a Vercel SPA fallback,
   select the reviewed production API-target mechanism, and add exact-origin
   CORS regressions. This does not authorize dashboard writes or deployment.
4. **Publication/deployment approval:** after reconciliation and fresh Docker,
   backend, frontend, and browser checks, authorize a feature-branch push, PR,
   required checks/review, and merge. The approval must explicitly acknowledge
   that merge to `main` triggers the Vercel frontend and Render API deployments.
5. **Dashboard-change approval:** separately authorize the exact non-secret
   Vercel `VITE_API_URL`, Render `SMARTADVISOR_CORS_ORIGINS`, and any Render
   Python-versus-Docker runtime change. No billing, plan, or live-provider flag
   change is implied.
