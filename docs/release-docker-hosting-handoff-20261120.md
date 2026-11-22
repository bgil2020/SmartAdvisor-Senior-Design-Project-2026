# Release, Docker, and hosted-routing handoff

Updated offline on 2026-11-21. No provider, syllabus-source, hosted POST,
deployment, dashboard write, or billing action was performed during this work.

## Release candidate

- Published `origin/main`: `e0bfb0fc61cc3501d8154a98ccac97a3fcf6c245`.
- Container-tested release candidate: `9908adff25c0106078fca163679d026da09d7cdc`.
- Current main was merged into the release branch, preserving its DARS and
  semester-history work alongside the parser and grading safeguard commits.
- `c7b241544a46498f6a99fa508d279ca96085b84c` contains the parser fix and the
  passed single-turn live grading diagnostic.
- `7a932fc04cd2d5883848a5d33ea1f03c95c8b2ae` contains the production grading
  safeguard, verified offline only.
- `4f8a772b983e8658c827aa909891c5cc26c35d49` is the evidence closeout. The
  earlier instruction to checkpoint the numeric-checker correction is stale:
  that work is already checkpointed in this ancestry.
- The two-turn live acquisition + Gemini + follow-up evidence-reuse workflow
  remains unverified.

The isolated worktree is
`D:\Projects\SmartAdvisor-Senior-Design-Project-2026\.worktrees\main-verified`.
Local-only acquisition evidence remains untracked and excluded from Docker's
build context. It must not be staged or published accidentally.

## Docker verification

Docker Desktop Linux engine 29.9.3 ran without a settings change. Attempt 1 on
the reconciled tree passed application, route, asset, and process assertions,
then stopped on a PowerShell-native stderr handling defect while reading the
Xvfb log. The container was removed. The narrow log-capture correction was
committed and tested before attempt 2.

Attempt 2 passed using commit
`9908adff25c0106078fca163679d026da09d7cdc` and image
`sha256:5b54cf659d631b85b27d11179ed93c7a2e3626c567326934b29884f972d3dd5b`.
Docker applied 512 MiB memory, 512 MiB memory+swap (zero additional swap), and
restart policy `no`. Health, `/`, `/forms`, `/chatbot`, two real static assets,
catalog GET, JSON 404 handling, synthetic headed Chromium, Xvfb/Uvicorn state,
and Chromium cleanup passed. Acquisition and provider traffic were disabled;
no conversation request ran. Idle usage was 149.7 MiB. Authoritative cgroup
peak was 456 MiB, leaving 56 MiB peak headroom. Docker's point-in-time sampled
peak was 149.7 MiB; the browser-family RSS diagnostic was 900.5 MiB because it
double-counts shared pages and is not a cgroup measurement. There were zero
restarts and no OOM kill. Graceful stop produced exit 143, and the test
container was removed.

## Applied hosting facts

- GitHub Actions run `45010467762` successfully deployed Vercel production from
  main commit `e0bfb0fc61cc3501d8154a98ccac97a3fcf6c245` on 2026-11-22.
- Vercel project reported by that workflow: `smartadvisor-group17-main`.
- Production alias: `https://smartadvisor-group17-main.vercel.app`.
- Current `/` returns 200; direct `/forms` and `/chatbot` return 404.
- The current production bundle targets
  `https://smartadvisor-group17-demo.onrender.com`.
- That backend's `/` and `/courses?term=202608` return 200.
- An exact-origin preflight from the production Vercel origin returns 200 with
  `Access-Control-Allow-Origin` equal to that exact origin and methods
  `GET, POST`.

Authenticated browser access to the Vercel and Render dashboards was not
available in this chat, and no local Vercel/Render CLI session or token was
present. Consequently the applied Render commit, runtime, plan, branch,
auto-deploy setting, preview behavior, and environment-variable presence/scope
remain unknown. Vercel's dashboard Git integration and variable scopes are also
unknown. The repository GitHub workflow is independently configured to attempt
a production Vercel deployment on every push to `main`; Render deployment on
merge remains unknown until its applied service settings are inspected.

## Offline hosting corrections under review

- `frontend/vercel.json`: official Vercel SPA fallback to `index.html`.
- `backend/api.py`: extensionless SPA fallback for the single-container build,
  mounted after API routes; exact CORS-origin parsing is now directly tested.
- `infra/render.yaml`: selects the root Dockerfile and Docker build context with
  a `/` health check. Repository edits do not change an existing Render service
  unless its applied Blueprint/service configuration consumes them.
- `scripts/verify_container_512mb.ps1`: stronger limits, traffic-disablement,
  process, route, memory, restart/OOM, and cleanup assertions.
- `.dockerignore`: excludes acquisition evidence from the image context.
- `Dockerfile`: normalizes the Linux entrypoint line endings.

The frontend continues to use the build-time `VITE_API_URL`. The currently
deployed value resolves to the intended public Render endpoint, so no backend
URL was hard-coded into source. Before release, confirm the production-scoped
Vercel variable remains set to that endpoint. The Render exact-origin CORS
behavior is currently correct, but its applied variable scope is unknown.

## Dependency advisory scope

`npm audit --omit=dev` reports zero production dependency vulnerabilities.
The full audit reports 9 moderate and 2 high findings in development/build
tooling. The high findings are Vite's development-editor path and Zod reached
through ESLint tooling. The Docker final image copies only Vite's static build,
not frontend `node_modules`, and Vercel serves the built artifact. No deployed
end-user runtime exploit path was identified. The advisories remain documented;
no force fix or dependency upgrade was applied.

## Remaining approvals

1. Provide authenticated read-only dashboard access to establish Vercel and
   Render applied settings.
2. After all checks pass, authorize merge of the tested PR.
   A main push will make the GitHub Vercel production workflow run; Render's
   merge consequence is still unknown.
3. No dashboard changes are included in this release. Preserve production
   `VITE_API_URL` on Vercel and exact production
   `SMARTADVISOR_CORS_ORIGINS` on Render. The deployed Render service remains
   native Python/FastAPI/Uvicorn on its reported Free plan; this release does
   not convert it to Docker or publish `infra/render.yaml` changes.
