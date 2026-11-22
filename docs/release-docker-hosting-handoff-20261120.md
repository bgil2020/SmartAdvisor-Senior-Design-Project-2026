# Release, Docker, and hosted-routing handoff

Updated offline on 2026-11-21. No provider, syllabus-source, hosted POST,
deployment, dashboard write, or billing action was performed during this work.

## Release candidate

- Published `origin/main`: `0fca051c6b43108a8fc6d33a8566b26b19893c4f`.
- Local release candidate: `4f8a772b983e8658c827aa909891c5cc26c35d49`.
- The candidate is six commits ahead of and zero commits behind `origin/main`.
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

Docker Desktop Linux engine 29.9.3 started without a settings change. The
bounded verifier built the candidate plus the offline hosting changes and
created exactly one disposable runtime container with 512 MiB memory, 512 MiB
memory+swap, and restart policy `no`. Inspection confirmed acquisition and
provider traffic were disabled. The container exited before application
startup with code 127 because the Windows checkout supplied CRLF in the Bash
entrypoint (`bash\r`). It was not OOM-killed, did not restart, and was removed.

The Dockerfile now normalizes the copied entrypoint to LF and fails its build
if any CR remains. One separately approved replacement container used image
`sha256:ce9d9659021f11d91ffffa79aa163f545dcfbc70c36b82a5989153f0236414de`
from source manifest
`f8924f41e78ad694a25bbb34fbf325e45fcbd84ccc2a15f70d4f52a5152249f4`.
It reached API health under the applied 512 MiB memory and memory+swap limits,
used restart policy `no`, sampled 319.9 MiB idle, was not OOM-killed, did not
restart, and was removed after a graceful stop attempt. The verifier then hit a
Windows PowerShell `Invoke-WebRequest` legacy-parser exception before `/forms`.
Therefore this is not a complete runtime/browser pass: sampled/cgroup peak,
memory headroom, SPA routes/assets, Xvfb/Chromium state, and unknown-route
behavior were not established. `-UseBasicParsing` is now applied offline for a
future separately approved run. The sanitized failed-run record is local-only
at `.local-docker-verification-20261121.json`.

## Applied hosting facts

- GitHub Actions run `44645964260` successfully deployed Vercel production from
  main commit `0fca051c6b43108a8fc6d33a8566b26b19893c4f` on 2026-11-20.
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

1. If desired, separately approve one new bounded 512 MiB container to verify
   the offline-only PowerShell parser correction, direct routes,
   Xvfb/Chromium cleanup, and peak whole-container memory.
2. Provide authenticated read-only dashboard access to establish Vercel and
   Render applied settings.
3. After all checks pass, authorize push, PR, required review/checks, and merge.
   A main push will make the GitHub Vercel production workflow run; Render's
   merge consequence is still unknown.
4. Separately authorize any dashboard changes. Expected non-secret settings are
   production `VITE_API_URL` on Vercel and exact production
   `SMARTADVISOR_CORS_ORIGINS` on Render. Changing an existing Render service
   from native Python to Docker would rebuild/redeploy it and must be explicitly
   approved after runtime/plan/auto-deploy inspection.
