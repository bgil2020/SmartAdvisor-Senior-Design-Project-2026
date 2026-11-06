# Controlled Catalog Fetch-on-Miss

> **Development-branch capability; disabled by default and not production
> deployment.** This increment supports one course-description source per
> eligible `/conversation` request. It does not fetch syllabi.

This branch is stacked on the unmerged development dependencies
`feature/rag-atomic-storage`, `feature/rag-storage-assessment`, and
`feature/rag-evidence-readiness`. Reviewers should use the atomic-storage head as
the logical base and should not treat prerequisite commits as new acquisition
work.

## Supported path

The implemented path is:

```text
validated informational request
  -> local readiness assessment
  -> one eligible missing course_description plan
  -> approved schedule-course check
  -> exact FAU catalog sitemap resolution
  -> bounded detail-page collection
  -> existing parser and validator
  -> atomic operational generation publication
  -> process-local retriever activation
  -> one readiness/retrieval retry
  -> cited provider answer or cited excerpt fallback
```

Planning and execution remain separate. `acquisition_plan.execute` stays false;
the opt-in executor independently checks the validated route, resolved course,
one-category plan, evidence gap, operational storage state, and settings before
performing any request.

Acquisition is allowed only when the request is informational, exactly one course
is resolved, that course appears in the project's schedule dataset, the only
missing category is `course_description`, readiness marks the source absent and
eligible, operational storage is healthy, and acquisition is enabled.

There is no acquisition for local hits, clarification/conflicts, unsupported
questions, scheduling/compatibility/eligibility/advisor routes, an already
present source whose requested detail was not located, freshness uncertainty,
mixed catalog/syllabus plans, empty storage, or corrupt/recovery-mode storage.

## Configuration

Settings are read at request/process startup. Restart the server after changes.

| Setting | Default | Meaning |
| --- | ---: | --- |
| `RAG_CATALOG_ACQUISITION_ENABLED` | `false` | Explicit opt-in switch. |
| `RAG_OPERATIONAL_ROOT` | unset | Required initialized persistent operational store. |
| `RAG_CATALOG_ACQUISITION_ROOT` | `data/course_descriptions` | Ignored raw/candidate/cache location. |
| `RAG_CATALOG_REQUEST_TIMEOUT_SECONDS` | `10` | Timeout for each HTTP operation. |
| `RAG_CATALOG_TOTAL_DEADLINE_SECONDS` | `30` | Whole collection deadline, including retries/waits. |
| `RAG_CATALOG_PACE_SECONDS` | `0.25` | Sequential-source pacing. |
| `RAG_CATALOG_MAX_RETRIES` | `1` | Retry count for timeout/transport and 429/5xx only. |
| `RAG_CATALOG_MAX_RETRY_AFTER_SECONDS` | `2` | Maximum honored retry delay. |
| `RAG_CATALOG_MAX_REQUESTS` | `6` | Total discovery/detail/redirect/retry request limit. |
| `RAG_CATALOG_MAX_RESPONSE_BYTES` | `8388608` | Per-response streamed byte limit. |
| `RAG_CATALOG_MAX_REDIRECTS` | `1` | Per-request redirect limit. |
| Shared external-source slot | fixed `1` | Catalog and syllabus work share one process-wide slot; this is not environment-configurable. |
| `RAG_CATALOG_FAILURE_COOLDOWN_SECONDS` | `60` | Temporary failure/no-result cooldown. |
| `RAG_CATALOG_COORDINATION_CACHE_SIZE` | `128` | Maximum process-local cooldown entries. |

Only HTTPS `catalog.fau.edu` requests are permitted. Redirect targets are checked
before following. The executor never accepts a user/model URL and does no web
search or crawling. Persistent 401/403 outcomes are not retried. Temporary
failure cooldowns expire and are not permanent nonexistence claims.

## Storage initialization and startup

Checkout contains no populated operational store. Initialize it explicitly with
already validated candidate batches before enabling acquisition:

```powershell
python scripts/rag.py operational-import `
  --root data/rag/operational `
  --course-batch data/course_descriptions/candidates/<validated-batch>.json

python scripts/rag.py operational-inspect --root data/rag/operational
```

Then start one supported API process:

```powershell
$env:RAG_OPERATIONAL_ROOT = "data/rag/operational"
$env:RAG_CATALOG_ACQUISITION_ROOT = "data/course_descriptions"
$env:RAG_CATALOG_ACQUISITION_ENABLED = "true"
$env:RAG_GENERATION_MODE = "fallback"
$env:CONVERSATIONAL_PARSER_MODE = "deterministic"
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

An empty store returns `storage_uninitialized`; an unreadable/corrupt store
returns a storage limitation. Neither condition is concealed by downloading.

## Request and response

Example request for a supported schedule course whose description is absent:

```powershell
$body = @{
  message = "What topics does CAP2751 cover?"
  course_code = "CAP2751"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/conversation `
  -ContentType application/json `
  -Body $body
```

Inspect these response fields rather than assuming acquisition succeeded:

- `initial_evidence_decision`
- `initial_acquisition_plan` (still data-only with `execute=false`)
- `acquisition_enabled`, `acquisition_attempted`, `acquisition_outcome`
- `acquisition_reason`, `acquisition_coalesced`
- `acquisition_request_count`, `acquisition_redirect_count`,
  `acquisition_retry_count`
- `post_acquisition_evidence_decision`
- `active_corpus_generation`
- `generation_source`, `generation_fallback_used`
- `supporting_source_ids`, `rag_sources`

Possible outcomes include `not_needed`, `disabled`, `published`,
`local_evidence_available`, `source_not_found`, `access_denied`, `timeout`,
`temporarily_unavailable`, `response_too_large`, `request_budget_exceeded`,
`candidate_rejected`, `publication_failed`, `cooldown_active`, and storage
limitations. A successful publication can still end with
`requested_detail_not_located`; fetching a document is not proof that it answers
the question.

Repeat the exact request. A ready local hit reports `acquisition_attempted=false`,
`acquisition_outcome=not_needed`, and zero acquisition request counts.

## Coordination, cancellation, and deployment boundary

Requests for the same course are coalesced in one process. Waiting requests reuse
the leader's result and rerun readiness; a race that completes before collection
starts is rechecked against the active retriever. External concurrency and
failure cooldown state are bounded independently of the operational publication
lock. Network collection completes before acquiring the storage writer lock.

The FastAPI route runs synchronous parser/collector/storage work in a worker, not
on the event loop. Client disconnect sets a cooperative cancellation event. A
currently blocked socket still ends under its per-request timeout, but the worker
is awaited and checks cancellation before parsing and again before publication;
there is no detached timeout thread that can publish late.

This remains safe only for one supported backend process on one host with a
persistent writable filesystem. The catalog coordinator, cooldown, active
retriever, and cancellation state are process-local. Multiple workers/replicas,
ephemeral storage, and out-of-process hot reload remain unsupported. The backend
owner must resolve deployed topology before enabling acquisition outside local
development.

## Failure meaning and retained evidence

Raw pages, fetch manifests, caches, and candidates remain ignored local data.
Operational accepted records remain authoritative after atomic publication.
No automatic cleanup or retention decision is introduced.

`source_not_found` means no exact path appeared in the checked published sitemap;
it does not mean the university has no information. Denial, timeout, transport,
parse, validation, and publication failures remain distinct. Provider generation
never runs until readiness is `ready`; provider failure uses the existing cited
excerpt fallback.

Syllabus acquisition remains the next increment. Generic syllabus discovery is
separate and unimplemented. On the stacked syllabus branch, only exact tracked
mappings use the same shared slot; see
[Controlled Exact-Mapping Syllabus Fetch-on-Miss](rag-syllabus-acquisition.md).
