# RAG Coverage, Storage, and Performance Assessment

## Decision

**Verdict 2: a small storage prerequisite is required before API-triggered
acquisition.** Keep the file-based design for the next bounded increment, but add
one atomic publication primitive: an explicit operational accepted snapshot,
single-writer locking, a versioned/atomic corpus replacement, and an in-process
last-good retriever swap.

No SQLite, Supabase migration, vector database, crawler, automatic deletion, or
retrieval rewrite is justified by the measured dataset. This recommendation is
provisional until the backend owner answers:

> Will the next deployed FastAPI backend be one process/replica with a persistent
> writable volume preserved across deploys, or will it use ephemeral storage,
> multiple workers, or multiple replicas?

For one process on persistent storage, the safeguarded file design is adequate.
For ephemeral or multi-replica hosting, the team must choose shared persistent
storage with the backend owner before acquisition is connected.

## What was measured

Measurements used the existing ignored five-description/one-syllabus artifacts
read-only. No source or provider request was made. Timings ran on Windows 11,
Python 3.12.6, an AMD64 16-logical-CPU machine with 33.46 GB physical memory.
“First observed” does not mean disk-cold because the operating-system cache was
not controlled. Warm values are in-process medians.

| Artifact or operation | Measured result |
| --- | ---: |
| Catalog raw/cache | 21 files, 9,405,858 bytes |
| Syllabus raw | 1 file, 134,210 bytes |
| Catalog candidate | 1 file, 14,543 bytes, 5 records |
| Syllabus candidate | 1 file, 28,042 bytes, 1 record |
| Tracked accepted stores | 382 bytes total, **0 records** |
| Rollback history | 0 files |
| Serialized corpus | 21,943 bytes |
| Corpus coverage | 6 documents, 19 chunks, 5 courses |
| Searchable chunk text | 5,581 characters / 5,600 UTF-8 bytes |
| Exact duplicate chunk groups | 0 |
| Repeated sentence groups across chunks | 1; 324 extra characters |
| Exact raw duplication beyond one copy | 4,700,698 bytes |
| Warm corpus JSON load | 0.185 ms median; 0.202 ms p95 |
| Warm model validation/index build | 0.310 ms median; 0.356 ms p95 |
| Warm lexical retrieval | 0.010 ms topics; 0.055 ms quiz median |
| Warm readiness assessment | 0.016 ms topics; 0.105 ms quiz median |
| Current service reread/reindex/answer | 0.694 ms median; 0.728 ms p95 |
| Isolated six-record rebuild | 1.025 ms median; 1.122 ms p95 |

The catalog batch and `_cache` intentionally retain five identical HTML pairs:
the batch is an audit snapshot while `_cache` supports conditional requests. That
explains almost all 4.70 MB duplication. It is worth addressing only if retained
raw history grows; it is not a blocker at current scale.

The syllabus candidate intentionally repeats normalized source text as
`document_text`, `exact_source_text`, and heading-scoped sections. The corpus
then repeats selected source metadata per chunk so the serving snapshot is
self-contained. These copies are small relative to raw HTML.

No offline Gemini-compatible tokenizer was installed. The measured generation
prompts were 661 characters for COP4331 topics and 993 characters for EEL3111
quiz grading. Character-divided-by-four estimates were approximately 165 and 248
tokens; these are **not measured provider token usage** and do not imply Gemini
latency.

## Existing data flow and authority

| Stage | Current storage/read-write behavior | Authority and duplication |
| --- | --- | --- |
| Supported schedule data | `data/FAU_Courses.xlsx` is loaded once when `backend.api` imports. It contains 913 Fall 2026 rows/CRNs and 139 normalized course codes. | Authoritative for prototype schedule/section operations, not catalog descriptions or syllabus policy. |
| Catalog discovery | The tracked five-course manifest records known mappings. A fetch command resolves any requested exact course code against the published sitemap and records the result in its fetch manifest. | The live sitemap response is discovery evidence; the batch manifest is its local snapshot. A course being in the schedule workbook does not prove a catalog URL exists. |
| Syllabus discovery | The tracked manifest contains only three exact Fall 2026 document identities/URLs. | Authoritative mapping for those identities only. Generic course/term/section discovery is not implemented and must not be guessed. |
| Raw evidence | Catalog HTML/metadata live under a batch plus shared `_cache`; syllabus rendered HTML lives under its raw batch. | Raw content plus its hash is audit evidence. Cache duplication is intentional today. Git exclusion is not retention authorization. |
| Candidate | Offline parsers write normalized candidate batches; validators check identity, provenance, hashes, and content. | Validated candidate is provisional. It should not become runtime authority merely because validation passed. |
| Accepted/history | `accept_batch` is designed to merge by stable record ID, increment versions on changed content, and snapshot prior accepted files for rollback. | Intended normalized authority, but both actual tracked accepted stores are empty and no history exists. The demo corpus bypassed this stage and imported validated candidates directly. |
| Corpus/chunks | Explicit import validates inputs and writes one self-contained JSON corpus. Document and chunk IDs preserve source/version/scope metadata. | Derived serving artifact, not source authority. Current writes use direct `Path.write_text`, not atomic replace. |
| Runtime retrieval | Each information request calls `LexicalRetriever.from_path`, rereading JSON and rebuilding terms/IDF. | No RAG runtime cache. At 21.9 KB this is fast, but it provides no atomic last-good swap during updates. |
| Other runtime/cache | The schedule DataFrame is loaded once. Catalog `_cache` is a persistent HTTP revalidation cache. There is no generated-answer cache. | Answer caching is deferred; source freshness and authorization matter more than saving milliseconds. |
| Frontend | Backend responses include decision, scope, source ID, URL, locator, hashes, generation/fallback status, and acquisition plan. | The current TypeScript contract/UI does not expose the full RAG/readiness metadata. It receives no raw HTML, but UI integration remains future work. |

## Coverage and discovery

Actual validated searchable coverage is:

- Course-wide descriptions: `CAP4773`, `CDA4102`, `COP4331`, `EEL3111`, and
  `EGN4950C`.
- Syllabus: EEL3111, term `202608`, section `001`.
- Manifest-only syllabus identities: CAP4773-001 and COP4331-002 for term
  `202608`; their earlier observations were access-denied and they are not
  validated syllabus evidence.

The schedule workbook has 139 course codes and 913 course-section/CRN rows for
term `202608`. This is a supported scheduling list, not RAG source coverage.

For an unfamiliar course description, the implemented catalog collector can ask
the published sitemap for an exact course-code mapping within its request budget.
For an unfamiliar syllabus identity, no general discovery adapter exists. The
only supported route is a known exact manifest identity or a separately reviewed
manual discovery step. The system must clarify term/section and must not construct
or guess a document URL.

### Initial coverage recommendation

Keep the existing five descriptions and one syllabus as the acquisition
increment's acceptance set. Add a source only when a named classroom/product
scenario requires it and the readiness plan resolves an eligible exact identity.
Do not collect 15–25 descriptions or 3–5 syllabi merely to meet a suggested
count. A useful next acceptance exercise is one missing catalog description for
an explicit course already present in the 139-course scheduling list; syllabus
acquisition should wait for an authorized exact discovery rule.

## Deployment/storage options

### A. File-based with small safeguards — recommended now

- **Complexity:** lowest; reuses current schemas, validators, collectors, and
  corpus format.
- **Persistence:** adequate only on a persistent writable volume.
- **Concurrency:** safe with one acquisition writer, atomic rename, and readers
  holding an immutable in-memory snapshot.
- **Performance:** measured file/index costs are below 1 ms at current scale.
- **Recovery:** versioned accepted/corpus snapshots and a last-good pointer are
  simple to inspect and restore.
- **Retention:** raw/candidates remain separable from normalized/current serving
  data.

### B. SQLite — not justified yet

SQLite would add transactions, indexed metadata lookup, and safer single-host
concurrent writes. It would still need filesystem/object storage for raw HTML and
would introduce schema/migration/backup work. Current volume and lookup timing do
not justify it. Reconsider if a single persistent server develops substantial
concurrent write/history/query needs.

### C. Existing project database/storage — coordinate, do not duplicate

Supabase/PostgreSQL schema and scripts exist for courses, sections, risk rules,
and synthetic profiles, but runtime integration is explicitly inactive and the
schema has no RAG source/version/chunk contract. Use it only if the backend owner
selects shared storage for multi-replica or ephemeral hosting. Do not independently
add competing RAG tables or object storage.

## Small storage contract for the next increment

### Retained backend state

1. **Discovery record:** approved source adapter, exact source URL/document ID,
   course, category, term/section where applicable, and discovery time.
2. **Raw evidence:** bounded response/rendered document, response metadata, raw
   hash, and collection time. Collection time is not an effective date.
3. **Candidate:** normalized record plus validation outcome.
4. **Operational accepted snapshot:** the authoritative normalized current record,
   stored under an ignored/configurable persistent data root rather than silently
   populating tracked empty templates.
5. **Version history:** previous accepted metadata/content hashes and enough data
   for explicit rollback.
6. **Serving corpus:** derived, immutable/versioned JSON containing chunk text and
   traceable metadata.

The frontend receives only answer/readiness status, resolved scope, generation
status, source ID/version/category, applicability, URL, locator, content hash, and
limitations. It does not receive raw HTML, candidate paths, browser state, or
backend filesystem paths.

### Identity, deduplication, and rebuilding

- Stable document ID identifies source/category/course and syllabus
  term/section/document identity.
- `content_sha256` identifies content revision; collection timestamps never
  create a new revision.
- Unchanged hashes retain record version and skip corpus rebuilding.
- Chunk ID remains derived from document ID, locator, and content hash.
- Chunks should continue storing their selected text. At current scale, a
  self-contained immutable serving snapshot is safer and faster than resolving
  text references during every request.

### Atomic publication and last-good behavior

1. Acquire into a unique temporary batch; never write over current data.
2. Parse and validate fully.
3. Under a single-writer lock, compare content hashes and atomically publish the
   accepted snapshot using a same-directory temporary file plus `os.replace`.
4. If content changed, build and validate a new versioned corpus temporary file.
5. Atomically switch the current-corpus pointer/name only after validation.
6. Load a new retriever and atomically swap the process reference. In-flight
   readers finish on the old immutable snapshot.
7. On any failure, retain the prior accepted snapshot, corpus, and in-memory
   retriever.

For a single process, use one acquisition writer and immutable reader snapshots.
For multiple workers, every worker needs a pointer watcher/reload signal; for
multiple replicas, choose shared persistent storage first.

### Provisional operational limits

These are guardrails to evaluate, not scale claims:

- one resolved acquisition plan at a time;
- at most one catalog document and one syllabus document per plan;
- one validation/import attempt and at most one retrieval retry;
- 2 MiB raw catalog response and 5 MiB rendered syllabus response;
- 250,000 normalized characters and 100 chunks per document;
- 250 documents, 5,000 chunks, or 50 MiB serialized corpus before mandatory
  storage/design review;
- retain the existing collector request/deadline/denial limits.

### Retention and cleanup proposal

No automatic deletion should be enabled until the data owner approves retention
and redistribution rules. Until then, cleanup remains explicit/manual and every
target is reviewed.

After approval, a reasonable starting policy to review is: raw/candidate batches
30 days after successful promotion unless needed for audit; keep current accepted
records plus two prior versions; keep the last-good and previous corpus; never
persist browser profiles/cookies/session state. This is a proposal, not current
implemented behavior or authorization.

### Generation-context budget

Start with at most four chunks, at most 12,000 source-text characters total, and
at least one supporting chunk for every required request part. Prefer the most
direct locator and preserve complete relevant evidence; do not silently truncate
away a required part merely to reduce tokens. If the budget cannot support every
part, return partial/insufficient evidence rather than generate.

Evaluate the budget with stored character/UTF-8-byte measurements and retrieval
quality tests. If an official provider tokenizer/counting method is later used,
record its measured counts separately. Do not infer provider latency from these
offline timings.

Generated-answer caching is deferred: current retrieval is sub-millisecond, and
cache invalidation across source versions/scope/provider settings would add risk
without a demonstrated requirement.

## Updated task breakdown

| Work item | Status/outcome |
| --- | --- |
| Evidence readiness | Complete and published on `feature/rag-evidence-readiness`. |
| Storage/coverage assessment | Complete: keep file storage, but require atomic accepted/corpus publication and last-good in-memory swap. |
| Acquisition implementation | Next: implement the small publication primitive, then connect only eligible catalog plans; do not add generic syllabus discovery yet. |
| Reliability/evaluation | Follow-up: cooldown/coalescing, concurrent-reader tests, failure injection, last-good recovery, retention approval, and retrieval/context-budget evaluation. |

## Measured, inferred, and unknown

- **Measured:** actual saved file sizes/counts, corpus/chunk/text duplication,
  saved coverage, workbook coverage, generation context characters/bytes, load,
  index, retrieval, readiness, service, and isolated rebuild timings.
- **Inferred from code:** per-request RAG reload, direct non-atomic writes, intended
  accepted/history lifecycle, current frontend contract gap, and inactive database
  runtime.
- **Unknown:** final hosting topology/persistence, approved retention duration,
  redistribution permission, generic syllabus discovery method, realistic future
  acquisition frequency, and live provider latency/token usage.
