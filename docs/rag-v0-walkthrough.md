# RAG Information Engine v0 Walkthrough

> **Development-branch classroom demonstration; not production deployment.**
>
> Core RAG v0 is merged into `main`. The evidence-readiness extension in this
> guide applies to `feature/rag-evidence-readiness`; it is not production
> deployment. Locally acquired source data is not distributed by Git.

## A. What the demo shows

The implemented path is:

`bounded source acquisition -> offline parsing and validation -> explicit import and chunking -> lexical retrieval -> Gemini generation or cited excerpt fallback -> POST /conversation response`

The v0 route answers informational questions only. Scheduling, compatibility,
override screening, registration, and advisor-only decisions keep their existing
boundaries.

- **Catalog evidence** is course-wide description or prerequisite text. The
  verified sample covers `CAP4773`, `CDA4102`, `COP4331`, `EEL3111`, and
  `EGN4950C`.
- **Syllabus evidence** is term- and section-scoped. The verified sample adds
  EEL3111, term `202608`, section `001`.
- **Deterministic parsing** classifies a request and extracts course codes. It is
  separate from the optional provider call that writes a grounded answer.
- **Live generation** uses Gemini and must cite retrieved source IDs. The
  offline-safe default is a labeled source-excerpt fallback.
- **Manual acquisition** is an operator action. Asking a question never fetches
  missing data or performs automatic fetch-on-miss.
- **Implemented:** validated import, stable chunks, applicability filters,
  inspectable retrieval, provider citation validation, excerpt fallback, CLI
  access, and the `/conversation` information route.
- **Possible later work:** larger reviewed coverage, retrieval benchmarks,
  synonym/error analysis, controlled acquisition reliability, and frontend
  source rendering. These are not part of v0.

The previously verified full local corpus contained 6 documents, 19 chunks, 5
course codes, 5 catalog descriptions, and 1 syllabus. Those counts describe a
prepared local corpus, not files delivered by checkout.

### Request and evidence decision path

The active backend path reuses existing contracts rather than creating a second
router or provider stack:

1. `frontend/src/services/api.ts` can send the existing basic message payload,
   but the current UI does not expose readiness diagnostics or explicit RAG
   scope controls.
2. `backend/conversational_router.py` defines `ConversationRequest` and
   `ConversationResponse`, calls the parser, and dispatches the established
   policy result.
3. `backend/app/conversational/hybrid_parser.py` selects deterministic parsing or
   bounded Gemini parsing/fallback. `response_policy.py` preserves advisor and
   core-engine precedence and reconciles parsed RAG scope with optional API
   fields `course_code`, `term`, and `section`.
4. `backend/rag/readiness.py` classifies bounded evidence requirements and checks
   source applicability separately from passage support.
5. `backend/rag/service.py` loads `RAG_CORPUS_PATH`, invokes the existing lexical
   retriever, and permits `generation.py` only when every required part is ready.
6. The same `/conversation` response returns trusted corpus URLs/locators and
   generation provenance. The provider never invents source links.

Supported requirement categories are deliberately small: broad or specific
course topics require a Course Description; published prerequisites require a
Prerequisites passage; quiz/test/exam/assignment/project grading or policy
questions require an applicable syllabus plus term and section. A combined
topics/assessment request requires both. Scheduling, compatibility, eligibility,
and advisor actions remain outside RAG.

Readiness decisions distinguish `ready`, `clarification_required`,
`corpus_unavailable`, `appropriate_source_absent`,
`requested_detail_not_located`, `partially_supported`, and conflicting or
unsupported scope. A search score alone is never treated as sufficient support.
Unknown freshness remains `unknown`.

Machine-readable response fields include `evidence_decision`, `evidence_reason`,
`resolved_scope`, `required_source_categories`, `supporting_source_ids`,
`missing_evidence_categories`, `acquisition_eligible`, and `acquisition_plan`.
Plans always have `execute=false`: they identify the bounded existing collector
and unresolved gap but never perform a network request. Missing source can be
eligible for later controlled acquisition; requested content not located in an
already applicable document is not an automatic refetch trigger.

## B. Reproducible checkout

The repository documents Python 3.11+ and `requirements.txt`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On macOS/Linux, activate with `source .venv/bin/activate`. The normal
requirements include FastAPI, Uvicorn, pytest, python-dotenv, and
`google-genai`. Playwright is optional and is not needed for tests, import,
retrieval, or serving.

### Existing team clone

Protect local work first. Do not discard changes or force-switch:

```powershell
git status --short --branch
git fetch origin feature/rag-evidence-readiness
git switch feature/rag-evidence-readiness
git branch --show-current
git rev-parse HEAD
git rev-parse origin/feature/rag-evidence-readiness
```

If status is not clean or Git refuses the switch, stop. Commit the work on its
own branch or use a separate worktree; do not reset or clean it:

```powershell
git worktree add ..\SmartAdvisor-rag-readiness origin/feature/rag-evidence-readiness
Set-Location ..\SmartAdvisor-rag-readiness
```

That worktree is detached, which is sufficient for a demo. Create a new local
branch before making changes there.

### Fresh clone

```powershell
git clone https://github.com/bgil2020/SmartAdvisor-Senior-Design-Project-2026.git SmartAdvisor-rag-readiness
Set-Location SmartAdvisor-rag-readiness
git fetch origin feature/rag-evidence-readiness
git switch --track origin/feature/rag-evidence-readiness
git branch --show-current
git rev-parse HEAD
git rev-parse origin/feature/rag-evidence-readiness
```

The two hashes should match immediately after checkout.

## C. Configuration

Copy `.env.example` to `.env` only if useful. Never commit `.env`, paste a
credential into chat, or share one person's key. Process environment values take
precedence over values loaded from `.env`; explicit test constructor arguments
take precedence over both.

| Setting | Default | Purpose |
| --- | --- | --- |
| `CONVERSATIONAL_PARSER_MODE` | `deterministic` | Offline intent/entity parsing; `hybrid` separately enables the Gemini parser. |
| `GEMINI_API_KEY` | empty | Required only for live Gemini calls. Use `<YOUR_GEMINI_API_KEY>` as documentation, not a real key. |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Shared verified model default. |
| `GEMINI_TIMEOUT_SECONDS` | `5.0` | Bounded provider timeout. |
| `RAG_GENERATION_MODE` | `fallback` | `fallback` returns cited excerpts; `gemini` permits live generation. |
| `RAG_CORPUS_PATH` | `data/rag/local-corpus.json` | Local corpus path, relative to the repository root unless made absolute. |
| `RAG_OPERATIONAL_ROOT` | unset (`data/rag/operational` for operational CLI commands) | Enables the ignored, versioned operational accepted/corpus store. When configured, it takes precedence over `RAG_CORPUS_PATH` unless code/CLI supplies an explicit corpus path. |

Start a new server after changing settings. Imports load `.env` at process
startup, and an existing server will not reliably reflect later changes.

For the safe operational lifecycle, publish already validated candidates and
inspect the committed generation:

```powershell
python scripts/rag.py operational-import `
  --course-batch data/course_descriptions/candidates/<course-batch>.json `
  --syllabus-batch data/syllabi/candidates/<syllabus-batch>.json
python scripts/rag.py operational-inspect
$env:RAG_OPERATIONAL_ROOT = "data/rag/operational"
```

See [RAG operational storage and atomic publication](rag-operational-storage.md)
for commit-point, recovery, restart, and concurrency guarantees. This remains a
manual operator action and does not implement automatic acquisition.

### Optional controlled catalog fetch-on-miss

On `feature/rag-catalog-acquisition`, a missing course description can be
collected through `/conversation` only after the operational store has been
initialized and the feature is explicitly enabled:

```powershell
$env:RAG_OPERATIONAL_ROOT = "data/rag/operational"
$env:RAG_CATALOG_ACQUISITION_ROOT = "data/course_descriptions"
$env:RAG_CATALOG_ACQUISITION_ENABLED = "true"
$env:RAG_GENERATION_MODE = "fallback"
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

The course must already be present in the project schedule dataset and resolve
exactly through the published FAU catalog sitemap. The executor permits one
course-description source per eligible request, uses a 30-second total deadline,
10-second request timeout, six-request budget, one retry, one redirect, 8 MiB
per-response limit, one external acquisition at a time, a 60-second temporary
failure cooldown, and at most 128 cooldown entries.

On the first request, show `initial_evidence_decision`, `acquisition_outcome`,
request/redirect/retry counts, `post_acquisition_evidence_decision`, the active
generation, source URL, citation ID, and fallback status. Repeat the same request
and show `acquisition_attempted=false`, `acquisition_outcome=not_needed`, and zero
source requests. Expected values are illustrative; do not hard-code answer text.

See [Controlled Catalog Fetch-on-Miss](rag-catalog-acquisition.md) for failure
meanings, cancellation behavior, storage initialization, and deployment limits.
Syllabus fetch-on-miss and generic syllabus discovery remain unimplemented.

Offline retrieval/excerpt mode:

```powershell
$env:CONVERSATIONAL_PARSER_MODE = "deterministic"
$env:RAG_GENERATION_MODE = "fallback"
$env:RAG_CORPUS_PATH = "data/rag/local-corpus.json"
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

Live Gemini generation mode:

```powershell
$env:CONVERSATIONAL_PARSER_MODE = "deterministic"
$env:GEMINI_API_KEY = "<YOUR_GEMINI_API_KEY>"
$env:GEMINI_MODEL = "gemini-3.5-flash-lite"
$env:GEMINI_TIMEOUT_SECONDS = "10"
$env:RAG_GENERATION_MODE = "gemini"
$env:RAG_CORPUS_PATH = "data/rag/local-corpus.json"
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

Do not echo or screenshot the key. The parser can remain deterministic while RAG
generation uses Gemini; these are separate decisions.

Only manual syllabus acquisition needs Playwright. It is intentionally absent
from `requirements.txt`; install it only in a collection environment:

```powershell
python -m pip install playwright
```

The script uses an already installed Chrome executable and does not download a
browser runtime. If the default Windows Chrome path does not apply, pass
`--chrome <path-to-installed-chrome>`.

## D. Source data setup

Checkout does **not** include populated files under
`data/course_descriptions/raw/`, `data/course_descriptions/candidates/`,
`data/syllabi/raw/`, `data/syllabi/candidates/`, or
`data/rag/local-corpus.json`. Raw pages, third-party text, browser state, and
private reports remain excluded.

Run commands from the repository root. Batch IDs below are examples.

### Collect the five catalog descriptions

```powershell
python scripts/course_descriptions.py plan --courses CAP4773 CDA4102 COP4331 EEL3111 EGN4950C
python scripts/course_descriptions.py fetch --batch-id rag-v0-classroom --courses CAP4773 CDA4102 COP4331 EEL3111 EGN4950C --pace-seconds 1
python scripts/course_descriptions.py parse --batch-id rag-v0-classroom
python scripts/course_descriptions.py validate data/course_descriptions/candidates/rag-v0-classroom.json
python scripts/course_descriptions.py compare data/course_descriptions/candidates/rag-v0-classroom.json
python scripts/rag.py import --course-batch data/course_descriptions/candidates/rag-v0-classroom.json
python scripts/rag.py inspect
```

`fetch` is a bounded sequential network operation. Later commands are local.
RAG import validates the candidate and writes a local corpus; it does not modify
the tracked accepted dataset.

### Optionally collect the supported EEL3111 syllabus

Inspect the tracked identity and help without network access:

```powershell
python scripts/syllabi.py plan
python scripts/syllabus_browser_collect.py --help
```

Make one anonymous, visible, bounded attempt for EEL3111 Fall 2026 section 001:

```powershell
python scripts/syllabus_browser_collect.py --document-id a4bh2nqsq --batch-id rag-v0-eel3111 --visible
python scripts/syllabi.py parse --batch-id rag-v0-eel3111
python scripts/syllabi.py validate data/syllabi/candidates/rag-v0-eel3111.json
python scripts/syllabi.py compare data/syllabi/candidates/rag-v0-eel3111.json
```

The collector performs one logical navigation in a new nonpersistent context,
uses no login/profile/cookie reuse, stops on the first essential 401/403, permits
at most 2 failed essential responses and 60 total responses, defaults to a
20-second deadline, and closes the context/browser. Do not bypass access
controls, construct private requests, refresh repeatedly, or retry indefinitely.
A complete rendered document is saved only in the ignored raw batch directory.

Build the combined corpus:

```powershell
python scripts/rag.py import `
  --course-batch data/course_descriptions/candidates/rag-v0-classroom.json `
  --syllabus-batch data/syllabi/candidates/rag-v0-eel3111.json
python scripts/rag.py inspect
```

The verified local result was 6 documents and 19 chunks, including 9 usable
syllabus chunks. Counts can differ if official source content changes.

If syllabus collection is denied, incomplete, timed out, or unavailable, stop
after the catalog import. That **reduced-coverage catalog-only demo** supports
the COP4331 question and safe failure/fallback paths but cannot demonstrate the
section-specific EEL3111 policy. Do not promise another person's corpus.

Internal transfer of a candidate/corpus might improve classroom reliability,
but redistribution, retention, access, and versioning require separate data-owner
authorization. This branch does not upload or package source evidence.

## E. Classroom demo: 5-10 minutes

Prepare the corpus before class. Rehearse offline and restart in live mode only
when an authorized Gemini key and network are available. Output descriptions are
illustrative; source IDs may change when source content changes.

### 1. Inspect coverage (45 seconds)

**Action and command:**

```powershell
python scripts/rag.py inspect
```

**Observe:** input batches, counts, course coverage, and syllabus term/section.
The prepared full demo should show five courses plus EEL3111 `202608`/`001`.

**Proves:** the local index has explicit coverage.

**Say:** “Checkout ships the pipeline, not third-party text. This corpus was
built locally from validated candidates.”

### 2. Ask a supported catalog question (60 seconds)

```powershell
$env:RAG_GENERATION_MODE = "fallback"
python scripts/rag.py ask "What topics are covered in COP4331?" --course COP4331
```

**Observe:** `answered`, `source_excerpt_fallback`, a bracketed ID, and catalog
metadata. The previously verified ID was `rag:56eb050266e120e1`.

**Proves:** filtering, retrieval, citation propagation, and offline fallback.

**Say:** “This is a cited extractive fallback, not fresh model generation.”

### 3. Inspect the source passage (60 seconds)

```powershell
$corpus = Get-Content data/rag/local-corpus.json -Raw | ConvertFrom-Json
$corpus.chunks |
  Where-Object { $_.course_code -eq "COP4331" -and $_.locator -eq "Course Description" } |
  Select-Object chunk_id, document_id, course_code, record_category, locator, text |
  Format-List
```

**Observe:** the matching identity and exact indexed passage.

**Proves:** a citation can be traced to validated local evidence.

**Say:** “Citation validation confirms the retrieved passage identity; it does
not independently certify every generated statement.”

### 4. Ask the verified syllabus question (90 seconds)

Start the API in live mode as shown in C, then use another PowerShell window:

```powershell
$body = @{
  message = "What does the syllabus policy say about tests and quizzes for EEL3111 section 001?"
  term = "202608"
  section = "001"
} | ConvertTo-Json

$response = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/conversation `
  -ContentType application/json `
  -Body $body
```

**Observe:** EEL3111 term/section scope. The verified passage was
`rag:0ba6d6ca05eb62bb`, document
`fau-simple-syllabus:syllabus:eel3111:202608:001:a4bh2nqsq`, locator
`heading:Course Evaluation Method`. A changed source revision changes its ID.

**Proves:** `/conversation` reaches term/section-filtered syllabus evidence.

**Say:** “Syllabus evidence is section-specific; catalog evidence cannot replace
this policy.”

### 5. Show concise and full responses (90 seconds)

```powershell
$response | Select-Object `
  status, response_text, extracted_courses, generation_source, `
  generation_fallback_used, model_id, retrieved_evidence_count, `
  @{Name="source_ids"; Expression={ $_.rag_sources.source_id -join ", " }}, `
  @{Name="source_terms"; Expression={ $_.rag_sources.term_id -join ", " }}, `
  @{Name="source_sections"; Expression={ $_.rag_sources.section -join ", " }} |
  Format-List
```

Optional full JSON:

```powershell
$response | ConvertTo-Json -Depth 8
```

**Observe:** live success is `rag_answered`, `provider`, fallback false, model
`gemini-3.5-flash-lite`, and matching citations/scope. Provider failure remains
cited but is explicitly `source_excerpt_fallback` with a reason.

**Proves:** generation provenance and fallback state are visible.

**Say:** “The provider writes only after retrieval, and unknown citations are
rejected.”

### 6. Demonstrate safe failure (60 seconds)

```powershell
$env:RAG_GENERATION_MODE = "fallback"
python scripts/rag.py ask "Does COP4331 include field trips?" --course COP4331
python scripts/rag.py ask "What topics are covered in COP4331?" `
  --course COP4331 --corpus data/rag/does-not-exist.json
```

**Observe:** `no_relevant_evidence` and an actionable message; no provider call or
fetch occurs.

**Proves:** missing evidence fails closed.

**Say:** “This corpus cannot answer; that does not prove the fact is absent from
official sources.”

## F. API and frontend status

The backend path is verified. The API accepts optional `course_code`, `term`, and
`section` scope and returns readiness diagnostics. The existing frontend calls `/conversation` and
shows `response_text`, but its TypeScript response union/status card does not yet
model `rag_answered`, `no_relevant_evidence`, `rag_sources`, provider provenance,
or citation cards. Frontend build/tests alone are not RAG UI integration.

Demonstrate with PowerShell, `scripts/rag.py`, or FastAPI docs at
`http://127.0.0.1:8000/docs`. No new UI is included.

## G. Troubleshooting

- **Missing corpus/candidate:** checkout excludes local data. `rag.py inspect`
  needs a built corpus; `rag.py ask` returns actionable missing-corpus output.
  Run the explicit setup/import.
- **Missing dependencies/browser:** run `python -m pip install -r
  requirements.txt`. A Playwright error affects only optional collection; install
  it separately or use catalog-only coverage. No browser runtime is downloaded.
- **Wrong interpreter:** check `python --version`, `python -c "import sys;
  print(sys.executable)"`, and `python -m pip --version`. Use the same Python
  3.11+ environment for pip, pytest, and the server.
- **Missing/invalid Gemini config:** use fallback offline. For live mode, set an
  authorized key privately and `GEMINI_MODEL=gemini-3.5-flash-lite`; never print
  or commit the key.
- **Wrong model/stale settings:** stop with `Ctrl+C`, verify non-secret settings
  in the launch shell, and restart. Editing `.env` does not update a live process.
- **Port occupied:** choose another port, for example `--port 8011`, and use it
  in the request URL.
- **Collection denied/incomplete/timed out:** respect the outcome. Check only the
  manifest identity, Chrome path, and package setup. Do not reuse browser state,
  alter identity to evade a rule, replay private requests, or retry indefinitely.
- **No passage:** inspect coverage, spelling, course, term, and section; inspect
  the candidate and rebuild explicitly. Corpus absence is not official absence.
- **Provider fallback:** retrieval succeeded, but generation was disabled,
  unavailable, timed out, or rejected. This is not a retrieval failure.
- **Invalid citation/metadata:** the provider path rejects missing/unknown IDs.
  Compare bracketed IDs with `rag_sources[].source_id` and verify category,
  course, term, section, locator, URL, and source version.

| Stage | Diagnostic | Meaning |
| --- | --- | --- |
| Collection | raw batch absent or result denied/incomplete | No source evidence acquired. |
| Validation/import | invalid candidate or corpus absent | Evidence was not admitted to the RAG corpus. |
| Readiness | `appropriate_source_absent` | Required validated document/scope is absent; a later bounded acquisition may be eligible. |
| Readiness | `requested_detail_not_located` | Applicable source exists but checked passages do not support the detail; do not repeatedly refetch unchanged content. |
| Readiness | `partially_supported` | At least one requested part lacks support; no combined generation runs. |
| Generation | sources exist but fallback reported | Retrieval worked; provider generation did not. |

## H. Classroom backup plan

Prepare and inspect the corpus before class rather than collecting live.

1. Show `rag.py inspect` and the catalog query in offline fallback mode.
2. Show the indexed passage and matching citation.
3. Use the syllabus query in fallback mode only if authorized local evidence was
   prepared earlier; otherwise label the demo catalog-only.
4. A saved November 1 response may be shown only as **historical recorded live
   evidence**. It is not fresh generation and does not establish current
   provider/site availability.

Excerpt fallback proves retrieval and traceability, not live Gemini generation.

## I. Limitations and cleanup

- Coverage is five descriptions and one EEL3111 syllabus, not the full catalog.
- Fetching is manual and bounded; there is no fetch-on-miss.
- Live generation depends on provider/network/quota/model/key availability.
- Lexical retrieval is small and does not establish completeness.
- Retention/redistribution are unresolved; source evidence stays local/ignored.
- The frontend does not expose RAG provenance/source cards.
- Core RAG v0 is merged; the evidence-readiness extension remains an unmerged
  development feature and is not production deployment.

Stop the server with `Ctrl+C`. Inspect local evidence before any cleanup:

```powershell
git status --short --ignored -- data/course_descriptions data/syllabi data/rag
```

Do not use broad cleanup commands. If local policy authorizes removal, delete
only a specifically reviewed batch/candidate and `data/rag/local-corpus.json`.
Git cannot restore ignored evidence.

This readiness update is branch-scoped. Before merging it to `main`, the team
must review the acquisition contract and separately decide third-party data
treatment. Automatic acquisition remains a later task.

## Verification and contribution record

Historical RAG-v0 results remain historical. The readiness branch handoff/PR must
state newly executed baseline, focused, full-suite, real-corpus, and HTTP results
instead of presenting older counts as fresh. Automated tests remain offline;
live collection and provider calls are separate explicitly reported activities.

The syllabus parser/browser guard builds on bounded adapter and circuit-breaker
work from the peer's `test/syllabus-parser` branch. Selected commits were
integrated and adapted; the peer branch itself was not merged.
