# Controlled Exact-Mapping Syllabus Fetch-on-Miss

> **Development-branch capability; disabled by default. Generic syllabus
> discovery is not implemented.**

This branch is stacked on `feature/rag-catalog-acquisition`, which itself depends
on atomic storage, the storage assessment, and evidence readiness. Reviewers
should use the catalog-acquisition head as the logical base.

## Exact supported scope

Automatic execution requires one informational syllabus plan with explicit
course, term, and section plus an exact tracked manifest mapping. The executor
does not derive document IDs, construct URLs, accept user/model URLs, infer a
term from cached evidence, or substitute another section.

The current manifest contains three exact Fall 2026 identities:

| Scope | Document ID | Automatic treatment |
| --- | --- | --- |
| EEL3111 / `202608` / `001` | `a4bh2nqsq` | Eligible because a prior bounded session verified anonymous full-document access. |
| CAP4773 / `202608` / `001` | `fjhz2vvga` | `manual_collection_required`; the recorded observation is access denied. |
| COP4331 / `202608` / `002` | `sb4d8l8wb` | `manual_collection_required`; the recorded observation is access denied. |

No mapping means `source_unresolved` and zero browser activity. Existing
applicable syllabus evidence means no acquisition. An existing syllabus whose
requested detail is not located is never refetched.

## Request path

```text
/conversation validated syllabus request
  -> readiness: appropriate source absent
  -> exact manifest lookup by course + term + section
  -> one shared process-wide external-source slot
  -> killable headless browser child process
  -> existing browser guard and rendered-document parser
  -> existing syllabus validator
  -> atomic operational publication and runtime swap
  -> one readiness/retrieval retry
  -> cited answer/fallback or accurate limitation
```

Catalog HTTP work and syllabus browser work share the same single external-source
slot. Deduplication and cooldown keys include course, term, section, and document
ID, so different sections are never coalesced accidentally. Collection completes
outside the operational publication lock.

## Browser safety and bounds

The existing collector runs headless in a separate process using an installed
Chrome executable and optional Playwright Python package. It creates a fresh
nonpersistent context with no profile, imported cookies, login, stealth, or
download support. Service workers are blocked.

Only the exact tracked HTTPS `fau.simplesyllabus.com/doc/<document-id>/...` URL
is supplied. Top-level navigation and final document URL must stay on that host
and document path. Subrequests are classified as essential document, telemetry,
or other untrusted page resources and count toward the total response cap; page
content cannot supply a new navigation target.

Default bounds:

- one logical navigation;
- 20-second browser-render deadline and 30-second parent deadline;
- 60 observed responses total;
- two failed essential responses;
- immediate stop on the first essential 401/403;
- one process-wide external-source task across catalog and syllabus work;
- 300-second temporary failure cooldown;
- 128 exact-scope cooldown entries.

Successful initialization responses are counted but do not consume the
essential-failure budget. Telemetry failures do not override an otherwise usable
rendered document.

On API disconnect or parent deadline, the browser process tree is terminated and
waited for. The parent checks cancellation again before parsing and publication,
so a stopped child cannot later publish. Success, denial, incomplete extraction,
normal error, and timeout all close the page/context/browser during normal script
cleanup; forced termination is the bounded fallback.

Each attempt also writes bounded sanitized request diagnostics to the ignored
acquisition root. The response exposes an opaque `acquisition_diagnostic_id`, not
a local path. See [Exact-Mapping Syllabus Acquisition Diagnostic Checkpoint](rag-syllabus-diagnostics.md)
for the redaction contract, offline defects found, official documentation review,
and the proposed one-attempt verification gate.

## Configuration and setup

Syllabus acquisition has an independent switch:

| Setting | Default | Purpose |
| --- | ---: | --- |
| `RAG_SYLLABUS_ACQUISITION_ENABLED` | `false` | Explicit execution opt-in. |
| `RAG_SYLLABUS_ACQUISITION_ROOT` | `data/syllabi` | Ignored raw/candidate storage. |
| `RAG_SYLLABUS_CHROME_PATH` | Windows installed Chrome path | Existing browser executable; none is downloaded. |
| `RAG_SYLLABUS_BROWSER_DEADLINE_SECONDS` | `20` | Child render deadline. |
| `RAG_SYLLABUS_TOTAL_DEADLINE_SECONDS` | `30` | Parent wall-clock deadline. |
| `RAG_SYLLABUS_FAILURE_COOLDOWN_SECONDS` | `300` | Temporary failure/denial cooldown. |
| `RAG_SYLLABUS_COORDINATION_CACHE_SIZE` | `128` | Bounded exact-scope cooldown entries. |

Operational storage must already be initialized and healthy. The browser package
and configured Chrome executable must already exist; the API never installs or
downloads a runtime.

```powershell
$env:RAG_OPERATIONAL_ROOT = "<ignored-operational-root>"
$env:RAG_SYLLABUS_ACQUISITION_ROOT = "<ignored-syllabus-root>"
$env:RAG_SYLLABUS_ACQUISITION_ENABLED = "true"
$env:RAG_GENERATION_MODE = "fallback"
$env:CONVERSATIONAL_PARSER_MODE = "deterministic"
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

Example exact-scope request:

```powershell
$body = @{
  message = "How are quizzes graded in EEL3111-001?"
  course_code = "EEL3111"
  term = "202608"
  section = "001"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/conversation `
  -ContentType application/json `
  -Body $body
```

Inspect `initial_evidence_decision`, `initial_acquisition_plan`,
`acquisition_outcome`, `acquisition_document_id`, `acquisition_stop_reason`,
browser/essential response counts, `post_acquisition_evidence_decision`, active
generation, citations, source URL, and generation fallback fields.

## Validation and outcomes

The browser must yield a full rendered academic document, not a shell, thumbnail,
navigation page, or login. The existing parser and validator enforce course,
term, section, document identity, academic headings, source URL/locators, hashes,
and provenance. Existing corpus rules exclude instructor-contact and repeated
boilerplate headings from retrieval.

Outcomes distinguish `missing_required_scope`, `source_unresolved`, `disabled`,
`manual_collection_required`, `browser_unavailable`, `access_denied`, `timeout`,
`incomplete_extraction`, `identity_mismatch`, `invalid_candidate`,
`publication_failed`, `cooldown_active`, `published`, and local reuse. A failed
browser attempt is not evidence that the university lacks a syllabus or policy.
A successful import can still produce `requested_detail_not_located` after the
single retry.

Raw rendered HTML and candidates remain ignored local artifacts. Retention and
redistribution permission remain unresolved; no automatic deletion is added.

## Current live finding

On 2026-11-06, one API-initiated headless attempt for the exact EEL3111 mapping
reached an essential anonymous 403 and stopped with `essential_access_denied`.
No candidate was published and the active generation remained unchanged. The
identical second request was served from the process-local denial cooldown and
launched no browser. This verifies the executor and safe failure path, not live
automatic syllabus collection.

## Reconciliation with the earlier successful session

The November 1 and November 6 results are both retained. They used the same
tracked EEL3111 identity and the same literal manifest `view_url`, including the
descriptive path and `?mode=view`. Both used installed Chrome 156, a fresh
nonpersistent context, one navigation, no login/profile/cookie reuse, and the
same readiness heading and denial guard.

The saved evidence records these ordinary execution differences:

| November 1 manual success | November 6 automatic denial |
| --- | --- |
| Visible Playwright browser run directly by an operator. | Headless Playwright browser run in a killable child process. |
| Default service-worker behavior and no Playwright route handler. | Service workers blocked; top-level navigation constrained to the exact mapped document path. |
| 23 responses: one successful essential response, no essential failure, two redirects, and an unrelated telemetry 429. | 25 responses; four classified as essential before processing stopped at an essential 403. |
| Complete rendered page reached `Course Evaluation Method`. | No complete document was saved, parsed, or published. |

The automatic run retained only the sanitized `essential_document` category and
403 status, not the failing endpoint. Saved evidence therefore does not establish
that headless mode, service-worker handling, route interception, timing, or a
source-side change caused the difference. It also does not establish that the 403
was misclassified. There is no evidence-supported integration correction, so the
denial remains an access-denied result and no additional source probe was made.

### Supported prepared-syllabus path

When an authorized, previously validated candidate is already available locally,
publish it explicitly to ignored operational storage before starting the API.
This is not automatic acquisition and does not grant retention or redistribution
permission:

```powershell
python scripts/syllabi.py validate data/syllabi/candidates/<syllabus-batch>.json

python scripts/rag.py operational-import `
  --course-batch data/course_descriptions/candidates/<course-batch>.json `
  --syllabus-batch data/syllabi/candidates/<syllabus-batch>.json `
  --root <ignored-operational-root>

python scripts/rag.py operational-inspect --root <ignored-operational-root>
$env:RAG_OPERATIONAL_ROOT = "<ignored-operational-root>"
```

The reconciled offline check imported the saved five-description batch and the
saved EEL3111 candidate into an isolated store. Inspection reported 6 documents,
19 chunks, and EEL3111 `202608`/`001`. A real `/conversation` request then returned
`ready`, used one cited syllabus passage in excerpt-fallback mode, and reported
`acquisition_attempted=false` / `acquisition_outcome=not_needed`. No source or
provider request occurred.

Generic syllabus discovery, bulk collection, scheduled refresh, authenticated
access, and arbitrary document acquisition remain unimplemented.
