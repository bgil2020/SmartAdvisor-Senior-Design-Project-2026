# Bounded syllabus source adapter

This increment adds a syllabus source adapter without treating a library listing or JavaScript shell as a complete syllabus. It is deliberately limited to three exact documents and shares the course-description pipeline's HTTP controls and candidate/accepted/version/rollback lifecycle.

## Access finding (2026-10-30)

The test used a fresh anonymous HTTP client and an isolated Chrome profile with no FAU cookies or SSO state.

| Level | Observed result |
|---|---|
| Library shell | `https://fau.simplesyllabus.com/en-US/syllabus-library` returned HTTP 200 as a JavaScript application shell. |
| Search/filter | Anonymous browser rendering showed library results, including the exact three records below. No sign-in was requested for listing/search. |
| Full document | Each user-visible document route returned a 200 shell over ordinary HTTP. During normal anonymous browser rendering, the application-generated full-document request returned HTTP 403, leaving no complete document to extract. |
| Print/equivalent | The visible print route depended on the same unavailable full-document payload; it did not provide complete anonymous content. |

This is an observed access restriction, not a claim that every FAU syllabus is private. FAU's [Simple Syllabus guidance](https://www.fau.edu/canvas/additional-tools/simple-syllabus/) distinguishes “General Public” from “Campus Community” visibility. The [March 2026 provost memo](https://www.fau.edu/provost/documents/revisedsyllabimemomarch2026final.pdf) describes institutional repository policy; that policy statement does not override the observed 403 or establish collection/redistribution permission.

`robots.txt` had named disallow rules for GPTBot, Google-Extended, CCBot, and ChatGPT-User, but no wildcard rule was observed. The collector used its own identified academic-project user agent. That does not grant bulk-use or redistribution rights, so this adapter remains bounded and stores no live syllabus text in Git.

Selected exact results:

- CAP 4773, Fall 2026 1 Full Term (`202608`), section 001, document `fjhz2vvga`.
- COP 4331, Fall 2026 1 Full Term (`202608`), section 002, document `sb4d8l8wb`.
- EEL 3111, Fall 2026 1 Full Term (`202608`), section 001, document `a4bh2nqsq`.

The tracked [manifest](../data/syllabi/sample-manifest.json) preserves exact identities, instructors displayed in the public listing, view/print URLs, and restriction outcomes. Requested: 3; complete documents fetched: 0; restricted: 3; missing: 0; failed: 0.

## Placement and shared contract

- `backend/course_descriptions/http.py` is the small shared allowlist/retry/Retry-After primitive. The existing catalog fetcher delegates to it without changing its public interface.
- `backend/course_descriptions/storage.py` still defaults to the course-description validator/dataset, while allowing a source adapter to supply its validator and dataset ID. Compare now recognizes `restricted` outcomes.
- `backend/syllabi/` owns only syllabus-specific classification, identity, parsing, probing, and offline batch assembly.
- `data/syllabi/accepted.json`, the schema, and manifest are tracked. Accepted data starts empty.
- `data/syllabi/raw/`, `candidates/`, `.history/`, and `browser-profile/` are generated and ignored. Raw documents, extracted third-party text, caches, and sessions are not redistributed.

Both descriptions and syllabi use schema version 1.0 envelope fields: stable `record_id`, `record_category`, course/term/section scopes, exact source text, source URL/locators, evidence hash, content hash, timestamps, versions, unknowns, and limitations. Syllabus-specific content is not forced into `description`; it uses `document_text` and ordered `academic_sections`. This lets a future retrieval adapter consume both categories while retaining source identity and heading locators.

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

It diagnoses the server shell only. It does not claim to collect rendered text. A successful future access review may place one permitted, complete rendered HTML file at `data/syllabi/raw/<batch-id>/<source-document-id>.html`, then run:

```powershell
python scripts/syllabi.py parse --batch-id <batch-id>
python scripts/syllabi.py validate data/syllabi/candidates/<batch-id>.json
python scripts/syllabi.py compare data/syllabi/candidates/<batch-id>.json
python scripts/syllabi.py accept data/syllabi/candidates/<batch-id>.json
python scripts/syllabi.py rollback --batch-id <prior-accepted-batch-id>
```

Acceptance is explicit. Unchanged content retains its record and version; changed content increments the version. Omitted, missing, restricted, ambiguous, or failed items never delete previously accepted records. Collection timestamps are excluded from the content hash.

## Adding another document

Add no more than three exact supported records to the manifest, preserving the source document ID, course, term ID/name, section, and the visible document URL. Do not infer a section, replace a term, or copy content from another section. Obtain permission before supplying complete rendered HTML. The parser preserves exact heading-scoped text and does not infer workload, dates, or missing academic sections.

An authenticated adapter is a separate follow-up requiring explicit approval and an interactive account-holder session. It must not request or persist passwords, MFA codes, cookies, tokens, or reusable browser state.

## Limitations and next retrieval step

Coverage is currently zero complete live syllabi because all three selected payloads were restricted. Freshness is limited to the access check date. The smallest next RAG step is a read-only retrieval interface that maps both accepted datasets into passages while carrying `record_id`, `record_category`, scopes, source URL, and heading locator; embeddings and answer generation remain out of scope.

## Unsent data-team handoff

> The syllabus adapter is ready for permitted offline HTML, but the three Fall 2026 samples were listing-visible and full-document-restricted in an anonymous session. Do not treat the manifest as collected syllabus text. Please review visibility/redistribution authorization with the data owner. If a document is explicitly approved, provide complete rendered HTML through the ignored raw path, run parse/validate/compare, and review the candidate before explicit acceptance. Never send credentials or session artifacts.
