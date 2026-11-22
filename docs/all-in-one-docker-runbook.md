# All-in-one Docker demo runbook

Verified locally on 2026-11-22 at application checkpoint
`5e9b5010e6af7cf001e2af299a7deb641047597d` with image
`smartadvisor-allinone-browserfix:5e9b501` (image ID
`sha256:805de0dc1d40daa0ff470438ca140ef3cabb6ac3dd63d28d12dbcd48dda6039f`).
The image is a local demo candidate, not proof of hosted Docker operation.

## Rebuild the candidate

From the repository root at the checkpoint above:

```powershell
docker build `
  --build-arg SMARTADVISOR_SOURCE_FINGERPRINT=5e9b5010e6af7cf001e2af299a7deb641047597d `
  --tag smartadvisor-allinone-browserfix:5e9b501 .
```

Confirm the image label and ID before use:

```powershell
docker image inspect smartadvisor-allinone-browserfix:5e9b501
```

## Safe offline launch

This default launch keeps source acquisition and provider traffic disabled.
It uses an ephemeral evidence-signing key created only in the current shell:

```powershell
$signingBytes = New-Object byte[] 48
[Security.Cryptography.RandomNumberGenerator]::Fill($signingBytes)
$sessionSigningKey = [Convert]::ToBase64String($signingBytes)

docker run --rm --name smartadvisor-allinone-local `
  --restart no --memory 512m --memory-swap 512m `
  --publish 127.0.0.1:18000:8000 `
  --env PORT=8000 `
  --env ACQUISITION_BROWSER_MODE=headed `
  --env SYLLABUS_ACQUISITION_ENABLED=false `
  --env CATALOG_ACQUISITION_ENABLED=false `
  --env ACQUISITION_TEST_SYLLABUS_BUDGET=0 `
  --env ACQUISITION_TEST_CATALOG_BUDGET=0 `
  --env CONVERSATIONAL_PARSER_MODE=deterministic `
  --env RAG_GENERATION_MODE=fallback `
  --env GEMINI_API_KEY= `
  --env "SESSION_EVIDENCE_SIGNING_KEY=$sessionSigningKey" `
  smartadvisor-allinone-browserfix:5e9b501
```

Open `http://127.0.0.1:18000/`; readiness is
`http://127.0.0.1:18000/health`. Direct `/forms` and `/chatbot` routes are
served by the same container. Stop the foreground process with Ctrl+C; the
`--rm` container is disposable.

## Live-capable configuration boundary

Live source or Gemini activity requires separate explicit approval. Supply
credentials only to the runtime process (for example with Docker `--env`
using an already configured shell variable), never in the Dockerfile, image,
command history, repository, or diagnostic artifacts. The verified bounded
workflow used these non-secret settings:

- `CONVERSATIONAL_PARSER_MODE=deterministic`
- `RAG_GENERATION_MODE=gemini`
- `GEMINI_MODEL=gemini-3.5-flash-lite`
- `GEMINI_TIMEOUT_SECONDS=10`
- `GEMINI_MAX_OUTPUT_TOKENS=512`
- `GEMINI_TEST_REQUEST_BUDGET=2`
- `CATALOG_ACQUISITION_ENABLED=false`
- `ACQUISITION_TEST_CATALOG_BUDGET=0`
- `SYLLABUS_ACQUISITION_ENABLED=true`
- `ACQUISITION_TEST_SYLLABUS_BUDGET=1`
- `ACQUISITION_TIMEOUT_SECONDS=20`
- `ACQUISITION_MAX_RENDERED_HTML_BYTES=2097152`

Do not reuse those live-enabling values as unattended defaults. The application
honors an explicit `ACQUISITION_CHROME_PATH`; otherwise Windows uses its local
Chrome default and Linux uses Playwright's bundled Chromium discovery.

## Evidence scope

The structured local workflow record contains sanitized status, identity,
traffic, grounding, evidence-reuse, and budget metadata. The separately
redacted screenshot only demonstrates rendered UI state; it is not a substitute
for the structured record. Both remain local-only and are excluded from this
repository and the Docker build context.

The verified workflow completed two conversation submissions, one syllabus
acquisition, zero follow-up acquisitions, and two accepted Gemini generations.
It had zero OOM kills and zero restarts, but the cgroup peak reached the 512 MiB
limit and recorded 1,007 `memory.max` events. This is a bounded functional pass,
not a load or reliability qualification.
