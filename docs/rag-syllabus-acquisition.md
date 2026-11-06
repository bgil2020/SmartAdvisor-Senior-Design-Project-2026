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

The current manifest contains three Fall 2026 identities and one curated Spring
2027 identity. The schedule workbook remains Fall 2026-only; the CAP4613 entry
is an explicit source mapping, not scheduling coverage or generic discovery.

| Scope | Document ID | Automatic treatment |
| --- | --- | --- |
| EEL3111 / `202608` / `001` | `a4bh2nqsq` | Eligible because a prior bounded session verified anonymous full-document access. |
| CAP4773 / `202608` / `001` | `fjhz2vvga` | `manual_collection_required`; the recorded observation is access denied. |
| COP4331 / `202608` / `002` | `sb4d8l8wb` | `manual_collection_required`; the recorded observation is access denied. |
| CAP4613 / `202701` / `042` | `7w22o8n31` | Operator-launched anonymous collection is verified; the headless API attempt remains access-denied. |

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
download support. Browser behavior is part of each exact mapping: the original
Fall 2026 mappings block service workers; CAP4613 uses installed Chrome with
service workers allowed because that is the configuration reproduced
successfully in the operator-launched session. Context-level diagnostics observe
service-worker responses, but Playwright routing does not govern requests handled
inside a service worker. Exact top-level navigation/final-URL checks and rendered
identity validation still apply.

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
downloads a runtime. On the measured workstation Playwright 1.64.1 was installed,
its managed Chromium executable was absent, and installed Chrome `156.0.8078.80`
was used instead.

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
and provenance. Candidates preserve validated heading-scoped source text for
auditability and compatibility. Corpus construction—not parsing—excludes
`Instructor Information`, `Code of Academic Integrity`, `Policy on the Recording
of Lectures`, and `Artificial Intelligence Preamble` from retrieval. Existing
candidates that retain those sections remain valid, and no historical record or
hash is rewritten. PDF export is optional local evidence: a PDF failure does not
invalidate otherwise complete HTML, and a PDF success does not bypass HTML
validation.

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

### CAP4613 Spring 2027 result

On 2026-11-06, the user-reported PDF was not present in the scoped project or
attachment locations, so it could not be treated as independently validated.
The literal default `p.chromium.launch()` reproduction also could not start
because Playwright's managed Chromium executable was absent; it made zero source
requests. No browser runtime was installed.

One bounded operator-launched reproduction then used the already installed Chrome
156, a visible fresh nonpersistent context, service workers allowed, the exact
CAP4613 `202701` / `042` / `7w22o8n31` URL, one navigation, a 20-second browser
deadline, and the existing 60-response/first-essential-denial guard. It completed
without human interaction after launch: 24 responses were observed before
readiness, both essential responses were HTTP 200, and no access denial occurred.
The same session produced complete rendered HTML and a seven-page PDF. The PDF
visually confirmed CAP4613-042, Spring 2027 1 Full Term, course/evaluation/policy/
topical-outline content, and no shell or login page. The HTML parser produced one
valid record. The saved candidate has 12 retained academic sections because the
then-current parser omitted `Instructor Information`; the later compatibility
review restored the historical rule that candidates may retain it while corpus
construction excludes it. The saved candidate and accepted generation were not
rewritten. The PDF was reviewed visually page by page, but its text was not
independently machine-extracted and compared with the HTML candidate.

The separate headless `/conversation` attempt used the same installed Chrome 156,
service-worker setting, exact mapping, fresh context, and bounds. Readiness first
reported `appropriate_source_absent`, then the browser stopped on an essential
XHR 403 after 23 observed responses. The denied request was on the approved host,
carried the expected document identity, was not a navigation, was owned by the
main frame, and was not served by a service worker. No candidate, publication, or
runtime swap occurred. This is a genuine denied essential request under the
current classifier; it does not explain why headed and headless access differed.
No retry or browser-setting matrix was run.

### Headed worker feasibility and decision boundary

The successful run was operator-launched but noninteractive after process start.
The collector itself supplied the URL, waited for bounded academic readiness,
captured HTML/PDF, and closed the fresh context/browser. This is automated
collection with a visible browser, not manual text extraction.

It is technically possible to run the same explicit headed mode as a dedicated
worker. That does not make it part of the supported deployment or establish source
authorization:

- **Current Windows development host:** Playwright 1.64.1, installed Chrome 156,
  an interactive operating-system desktop/display session, writable ignored
  evidence storage, and the existing killable child-process wrapper are sufficient
  for the measured setup.
- **Possible Linux host:** Playwright documents that headed Linux execution needs
  a display such as Xvfb (`xvfb-run`) and matching browser/OS dependencies. Its
  browser documentation also requires a browser compatible with the installed
  Playwright version. The repository does not currently define a container, Xvfb
  service, or production host that supplies these prerequisites.
- **Lifecycle:** keep collection outside the publication lock; enforce one child,
  exact mapping, one navigation, response/deadline/denial limits, process-tree
  termination, `finally` cleanup, validation, then the existing single-process
  publication/runtime swap.
- **Deployment model:** operational publication remains supported only for one
  backend process on one host with persistent writable storage and one coordinated
  writer. Multiple workers/replicas or ephemeral storage need a different reviewed
  coordination/persistence design.
- **Secrets:** the browser path/display configuration is non-secret. Provider and
  other credentials remain server-side environment settings and must not be put in
  browser profiles, command logs, source artifacts, or Git.

Official references: [Playwright browsers and system dependencies](https://playwright.dev/python/docs/browsers),
[headed CI/Xvfb guidance](https://playwright.dev/python/docs/ci#running-headed),
and [service-worker routing behavior](https://playwright.dev/python/docs/service-workers).

The current headless result remains `headless_access_denied`. The explicit manifest
state makes the block reviewable and reversible, but no automatic
headless-denied-to-headed retry exists or is proposed. Enabling a headed worker
would require a deliberate configuration and separate deployment/source approval.

Backend-owner questions:

1. What operating system, host, and runtime will run FastAPI?
2. Will it provide a persistent writable volume across restarts and deploys?
3. Can it support a dedicated browser/display-capable worker, including installed
   browser dependencies and Xvfb or an equivalent display on Linux?
4. Can the deployment preserve one backend process/replica and the current
   single-writer/process-local runtime coordination assumption?

Source-access question to draft, not send:

> Is anonymous, noninteractive Playwright navigation to the exact public syllabus
> document, using a fresh browser context and bounded request limits, a permitted
> and supported integration for this project? If not, should the team use an
> institutional API, export, or approved document-transfer workflow instead?

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

The CAP4613 prepared path used a separate ignored operational root. Explicit
import of the validated candidate produced one document and nine chunks. Real
HTTP `/conversation` requests for quiz grading at `202701` / `042` returned
`ready` with exact syllabus citations in excerpt-fallback mode. Two identical
requests with acquisition enabled reported `not_needed`, zero browser responses,
and the same active generation. This verifies operator-launched collection,
validated publication, retrieval, citation propagation, and reuse; it does not
verify unattended acquisition.

One saved-data generation check then ran through real HTTP with deterministic
request parsing, acquisition disabled, and exactly one Gemini call. For “For
CAP4613 section 042 in Spring 2027, how are weekly quizzes weighted?”, readiness
was `ready`, acquisition was not attempted, and `gemini-3.5-flash-lite` returned
provider output with no fallback: weekly quizzes are 10% of the final grade. The
answer cited only `heading:Course Evaluation Method` from the exact `202701` / `042`
syllabus URL. That material claim matches the retained evidence. No university
request occurred.

Generic syllabus discovery, bulk collection, scheduled refresh, authenticated
access, and arbitrary document acquisition remain unimplemented.
