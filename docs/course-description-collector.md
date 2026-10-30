# Course Description Collector

This manual collector creates versioned, source-linked course-description records
for future retrieval ingestion. It is deliberately bounded to five requested
courses, does not crawl the catalog, does not fetch syllabi or schedules, and does
not change any current SmartAdvisor engine data.

## Architecture and placement

| Artifact | Location | Reason |
| --- | --- | --- |
| Fetch, parse, validation, and storage modules | `backend/course_descriptions/` | Reusable Python domain code belongs with active backend modules. Fetching, parsing, storage, and future consumption remain separate. |
| Manual entry point | `scripts/course_descriptions.py` | Existing administrative utilities use `scripts/`. Nothing runs unattended. |
| Canonical schema and accepted records | `data/course_descriptions/` | Shared file-backed data belongs under `data/`; descriptions are separate from section workbooks and compatibility data. |
| Offline tests and fixtures | `tests/test_course_description_collector.py`, `tests/course_descriptions/fixtures/` | Root pytest conventions; fixtures are synthetic, portable, and require no network. |
| Generated evidence and batches | `data/course_descriptions/raw/`, `candidates/`, `.history/` | Raw pages, transient candidates, and rollback snapshots are local generated artifacts and ignored by Git. |

The canonical record uses a stable `record_id` based on source, category, and
course—not on content. `content_sha256` identifies a revision. Course, term, and
section scopes are distinct; this source provides course scope only. The parser
preserves exact displayed text, extracts a full descriptive passage, and separates
only explicitly labeled prerequisite or prerequisite/corequisite lines.

The stable IDs, locators, hashes, explicit unknowns, and version fields were adapted
from earlier local source-preparation design work. Local reports, paths, approval
claims, and blanket public-only gates were not published or made dependencies.

## Access findings and limits

As checked on 2026-10-30, `https://catalog.fau.edu/robots.txt` says `Allow: /` and
advertises `https://catalog.fau.edu/sitemap.xml`. The public sitemap supplies actual
course-detail paths. Each detail page server-renders a `Course Description` field.
The `/courses/` listing is client-loaded and may show snippets, so it is never
accepted as full-text evidence. The visible catalog offers CSV export, but no
documented supported public API or feed was identified.

Robots guidance permits this bounded access but is not a content-redistribution
license. Consequently the repository tracks a reproducible five-course URL
manifest and synthetic fixtures, not downloaded HTML or live normalized text.
Before accepting live candidate text into the tracked `accepted.json`, the data
owner should confirm the repository's redistribution decision.

Collection is sequential with one-second default pacing, 20-second timeouts, two
bounded retries, capped `Retry-After` handling, a source-domain allowlist, and a
finite request budget. Persistent 403, 429, or server failures stop the remaining
course requests. Successful responses are cached; ETag or Last-Modified validators
are sent on later runs when the server provides them. Current pages did not expose
these validators during the initial check.

Catalog presence does not mean a course is offered in the scheduling workbook's
term. The collector therefore never assigns that term to catalog descriptions.
The current catalog page does not label a catalog edition or end date; records keep
those limitations explicit. `fetched_at` is collection time, not human verification.

## Clean-checkout setup

From the repository root, use Python 3.11+ and the normal project environment:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```

On macOS/Linux, use `.venv/bin/python` in place of `.venv/Scripts/python`.
No secret, browser, LLM, or additional dependency is required.

## Refresh workflow

The tracked sample manifest selects `CAP4773`, `CDA4102`, `COP4331`, `EEL3111`,
and `EGN4950C`. They occur in both active project catalogs and span five CECS-related
prefixes. Add or replace course codes by passing an explicit list of one to five
codes; the sitemap must contain an exact detail path or the result is `not_found`.

1. Plan without network access or writes to accepted data:

   ```bash
   python scripts/course_descriptions.py plan
   python scripts/course_descriptions.py plan --courses COP4331 CDA4102
   ```

2. Fetch a bounded list. Give the batch a stable name so later commands are clear:

   ```bash
   python scripts/course_descriptions.py fetch --batch-id fau-20261030-sample --courses CAP4773 CDA4102 COP4331 EEL3111 EGN4950C
   ```

3. Parse the cached pages offline and validate the candidate:

   ```bash
   python scripts/course_descriptions.py parse --batch-id fau-20261030-sample
   python scripts/course_descriptions.py validate data/course_descriptions/candidates/fau-20261030-sample.json
   ```

4. Compare without modifying accepted records:

   ```bash
   python scripts/course_descriptions.py compare data/course_descriptions/candidates/fau-20261030-sample.json
   ```

   The comparison reports `added`, `changed`, `unchanged`, `omitted`, `not_found`,
   `ambiguous`, and `failed`. Timestamp-only refreshes are unchanged. Omitted or
   failed courses never delete accepted records.

5. After inspecting sources, validation output, and redistribution suitability,
   explicitly accept the partial batch:

   ```bash
   python scripts/course_descriptions.py accept data/course_descriptions/candidates/fau-20261030-sample.json
   ```

   Acceptance merges valid records, retains omitted records, increments versions
   only for content changes, and stores the prior accepted file under ignored
   `.history/`. Fetching and parsing never overwrite accepted data.

6. Roll back to the prior accepted batch ID reported during acceptance:

   ```bash
   python scripts/course_descriptions.py rollback --batch-id initial-empty
   ```

## Inspect one record against its source

Open the record's `source.url` in a browser and compare `course_code`, `title`,
`exact_source_text`, `description`, and `prerequisite_text` with the page's Course
Description field. Confirm that `raw_sha256` matches the ignored cached HTML and
that `content_sha256` changes only when normalized title/description/prerequisite
content changes. Treat this as human review; an HTTP 200 alone is never a match.

## Verification

Normal regression tests are offline:

```bash
python -m pytest -q tests/test_course_description_collector.py
python -m pytest -q
```

The collector tests separately cover full extraction, listing-snippet rejection,
identity mismatch, missing/ambiguous text, stable IDs, duplicates, idempotency,
timestamp-only and content changes, partial omission, failed-fetch preservation,
bounded conditional HTTP behavior, acceptance, and rollback. A live check is the
explicit `fetch` command above and is not part of pytest.

## Future ingestion contract

A future RAG adapter should read only validated accepted records and map
`record_id`, `record_version`, `record_category`, scoped identity, exact text,
source locator, content hash, and limitations into the retrieval index. Adding a
valid record must not require retrieval or answer-generation code changes.
Workbook, future description, and eventual syllabus adapters should emit this same
core shape with category-specific metadata. Syllabus parsing, schedule fetching,
production RAG, vector indexing, answer generation, scheduled execution, and
automatic Git commits remain unimplemented.
