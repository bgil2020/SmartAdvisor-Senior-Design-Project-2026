# Bounded syllabus source adapter

This increment adds a syllabus source adapter without treating a library listing or JavaScript shell as a complete syllabus. It is deliberately limited to three exact documents and shares the course-description pipeline's HTTP controls and candidate/accepted/version/rollback lifecycle.

## Access finding (2026-10-30)

The test used a fresh anonymous HTTP client and an isolated Chrome profile with no FAU cookies or SSO state.

| Level | Observed result |
|---|---|
| Library shell | `https://fau.simplesyllabus.com/en-US/syllabus-library` returned HTTP 200 as a JavaScript application shell. |
| Search/filter | Anonymous browser rendering showed library results, including the exact three records below. No sign-in was requested for listing/search. |
| Full document | The exact tracked EEL3111-001 URL was tested directly in a clean Chrome profile. It redirected only to the locale-prefixed version of the same path, remained an empty shell, and its essential browser-generated document request returned HTTP 403. There was no login redirect, sign-in prompt, visible denial, iframe, main document, or academic text. |
| Library to document | The anonymous library rendered normally. Initializing it first and then navigating to the same exact tracked EEL URL produced the same empty shell and essential 403. |
| Print/equivalent | No complete document existed in the anonymous DOM, so the Print control could not be evaluated safely as a content source. The user's screenshot shows Print and Logout in their browser, which is consistent with a different session state but is not evidence of anonymous access. |

This is a generic anonymous access denial of unknown policy cause, not a claim that every FAU syllabus is private and not proof that login is explicitly required. FAU's [Simple Syllabus guidance](https://www.fau.edu/canvas/additional-tools/simple-syllabus/) distinguishes "General Public" from "Campus Community" visibility. The [March 2026 provost memo](https://www.fau.edu/provost/documents/revisedsyllabimemomarch2026final.pdf) describes institutional repository policy; that policy statement does not override the observed behavior or establish collection/redistribution permission.

### Root cause and corrected interpretation

The tracked URL and discovery were correct. The HTTP probe correctly found a JavaScript shell, but HTTP alone cannot determine the rendered outcome. A clean browser showed that the essential document request—not the unrelated Sentry telemetry failure—was denied. Because no explicit login UI or redirect appeared, the old generic `restricted` label overstated what was known. The status contract now distinguishes:

- `anonymous_full_document`
- `javascript_shell_awaiting_render`
- `explicit_login_required`
- `generic_access_denied`
- `explicit_automation_restriction`
- `unpublished_or_missing`
- parser-level incomplete extraction and identity mismatch outcomes

Rendered usable academic content wins over unrelated failed requests. A generic HTTP 403 is not converted to a login requirement.

### Robots and access-policy evidence

One logical request to the canonical `https://fau.simplesyllabus.com/robots.txt` produced this redirect chain:

1. `https://fau.simplesyllabus.com/robots.txt` — HTTP 302 to `/ui/locale-redirect?/robots.txt`.
2. `https://fau.simplesyllabus.com/ui/locale-redirect?/robots.txt` — HTTP 302 to `/en-US/robots.txt`.
3. `https://fau.simplesyllabus.com/en-US/robots.txt` — HTTP 200 `text/plain`.

The final `/en-US/robots.txt` is therefore the locale-resolved representation of the canonical root request, not conflicting policy. Its complete relevant rules are `Disallow: /` for four named agents: `GPTBot`, `Google-Extended`, `CCBot`, and `ChatGPT-User`. No wildcard group was present in the retrieved text.

The ordinary HTTP probe identifies itself as `SmartAdvisorSyllabusCollector/1.0 (manual academic project)`. The diagnostic browser used its native Chrome 156 user agent. Neither identity matches those four named tokens; neither identity was changed to evade a rule. This narrow robots observation does **not** establish authorization for automated document collection, explain the document 403, override terms or institutional controls, or grant redistribution rights. Applicable authorization remains uncertain, so no automatic live syllabus feed is claimed.

Selected exact results:

- CAP 4773, Fall 2026 1 Full Term (`202608`), section 001, document `fjhz2vvga`.
- COP 4331, Fall 2026 1 Full Term (`202608`), section 002, document `sb4d8l8wb`.
- EEL 3111, Fall 2026 1 Full Term (`202608`), section 001, document `a4bh2nqsq`.

The tracked [manifest](../data/syllabi/sample-manifest.json) preserves exact identities, instructors displayed in the public listing, view/print URLs, and access outcomes. Requested: 3; complete documents fetched: 0; generic access denied: 3; missing: 0; failed: 0. The new clean-browser reproduction focused on EEL3111-001 as directed; CAP4773-001 and COP4331-002 were not re-probed after EEL failed.

Browser evidence for this correction used installed Chrome 156 with a brand-new temporary `--user-data-dir`, no imported profile, no FAU login, and no cookies supplied by the user. There were three document navigation attempts (one `--dump-dom` preflight that was terminated after a reload loop, one instrumented direct navigation, and one instrumented navigation after the library) plus one library navigation. The two instrumented document attempts observed 37 essential document-response 403s caused by the application's reload loop (28 during the 25-second direct observation and 9 during the bounded library-first observation). The preflight did not capture per-request telemetry and is not included in that request count. No private request was constructed or replayed.

### Browser circuit breaker

`backend/syllabi/browser_probe.py` provides the driver-independent event guard for any later approved browser integration. Conservative defaults are:

- one logical document navigation per probe;
- stop and cancel on the first essential-document HTTP 401 or 403;
- at most two essential-document responses;
- at most 20 total observed responses, counted separately from logical navigation;
- telemetry responses counted separately and never used to invalidate otherwise complete rendered content;
- page/context closure on success, cancellation, stream exhaustion, or error.

The guard consumes only sanitized events observed during normal page navigation; it does not construct or replay a private request. Its denial loop, budgets, telemetry handling, cancellation, error cleanup, and accepted-data isolation are tested offline with a mock session. It was intentionally **not** tested with another live document request during closeout. The repository does not currently ship a concrete automatic browser driver, and live fetching remains blocked.

## Placement and shared contract

- `backend/course_descriptions/http.py` is the small shared allowlist/retry/Retry-After primitive. The existing catalog fetcher delegates to it without changing its public interface.
- `backend/course_descriptions/storage.py` still defaults to the course-description validator/dataset, while allowing a source adapter to supply its validator and dataset ID. Compare recognizes generic access-denied outcomes without deleting accepted records.
- `backend/syllabi/` owns only syllabus-specific classification, identity, parsing, probing, and offline batch assembly.
- `data/syllabi/accepted.json`, the schema, and manifest are tracked. Accepted data starts empty.
- `data/syllabi/raw/`, `candidates/`, `.history/`, and `browser-profile/` are generated and ignored. Raw documents, extracted third-party text, caches, and sessions are not redistributed.

Both descriptions and syllabi use schema version 1.0 envelope fields: stable `record_id`, `record_category`, course/term/section scopes, exact source text, source URL/locators, evidence hash, content hash, timestamps, versions, unknowns, and limitations. Syllabus-specific content is not forced into `description`; it uses `document_text` and ordered `academic_sections`. This lets a future retrieval adapter consume both categories while retaining source identity and heading locators.

The implemented ingestion path is deliberately manual and offline: an explicitly permitted complete rendered HTML file may be placed in the ignored raw batch directory, then parsed, validated, compared, and explicitly accepted. It is not a working automatic syllabus feed, and no live syllabus text has been accepted.

## Clean-checkout commands

No browser package or new dependency is required for offline use.

```powershell
python scripts/syllabi.py plan
python -m pytest tests/test_syllabus_collector.py tests/test_course_description_collector.py -q
```

The bounded HTTP diagnostic makes at most three document calls per attempt (six including one retry per document), sequentially by default:

```powershell
python scripts/syllabi.py probe
```

It diagnoses the server shell only. It does not claim to collect rendered text. To reproduce the browser finding, open the exact `view_url` from the manifest in a new Chrome Guest profile, confirm that no FAU session is present, and use DevTools Network plus Elements. Wait for either a document container with the expected course/section/term and academic headings, an explicit login/denial UI, or the essential document request to finish. Do not classify unrelated telemetry failures as document failures.

A successful future access review may place one permitted, complete rendered HTML file at `data/syllabi/raw/<batch-id>/<source-document-id>.html`, then run:

```powershell
python scripts/syllabi.py parse --batch-id <batch-id>
python scripts/syllabi.py validate data/syllabi/candidates/<batch-id>.json
python scripts/syllabi.py compare data/syllabi/candidates/<batch-id>.json
python scripts/syllabi.py accept data/syllabi/candidates/<batch-id>.json
python scripts/syllabi.py rollback --batch-id <prior-accepted-batch-id>
```

Acceptance is explicit. Unchanged content retains its record and version; changed content increments the version. Omitted, missing, access-denied, ambiguous, or failed items never delete previously accepted records. Collection timestamps are excluded from the content hash.

## Adding another document

Add no more than three exact supported records to the manifest, preserving the source document ID, course, term ID/name, section, and the visible document URL. Do not infer a section, replace a term, or copy content from another section. Obtain permission before supplying complete rendered HTML. The parser preserves exact heading-scoped text and does not infer workload, dates, or missing academic sections.

An authenticated adapter is a separate follow-up requiring explicit approval and an interactive account-holder session. It must not request or persist passwords, MFA codes, cookies, tokens, or reusable browser state.

## Limitations and next retrieval step

Coverage is currently zero complete live syllabi. The clean anonymous EEL attempt was generically denied at the essential browser request; the user's working page appears to have a different session state, as indicated by Logout, but no authenticated state was inspected or reused. Freshness is limited to the access check date. The smallest next RAG step remains a read-only retrieval interface after a permitted complete document is available; embeddings and answer generation remain out of scope.

During the latest diagnostic run, EEL3111-001 was the only document re-probed. CAP4773-001 and COP4331-002 were not re-probed. During this closeout, no syllabus document was requested; the only live access was the single allowed canonical robots request (three HTTP responses including redirects). No account/session reuse, sign-in, or bypass was attempted.

## Unsent data-team handoff

> The syllabus adapter is ready for permitted offline HTML, but the three Fall 2026 samples are listing-visible and have no anonymously collected full text. The clean EEL browser received a generic essential-request 403 without an explicit login prompt. Do not treat the manifest as collected syllabus text or infer that login is definitively required. Please review document visibility/redistribution authorization with the data owner. Never send credentials or session artifacts.
