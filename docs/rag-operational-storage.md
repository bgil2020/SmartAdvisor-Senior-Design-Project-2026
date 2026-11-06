# RAG Operational Storage and Corpus Publication

> **Development-branch storage prerequisite; automatic acquisition is not
> enabled.** This design supports one backend process on one host with a
> persistent writable filesystem and one coordinated publication writer.

## Decision and dependency

This implementation keeps the existing file-based RAG contracts. It depends on
the evidence-readiness work from `feature/rag-evidence-readiness` and the design
decision recorded on `feature/rag-storage-assessment`; neither dependency should
be omitted if this branch is reviewed independently.

The authoritative operational unit is one immutable generation:

```text
<operational-root>/
  generations/<generation-id>/
    accepted.json       # authoritative normalized records
    corpus.json         # derived self-contained chunks
    metadata.json       # schemas, counts, hashes, time meanings
  current.json          # atomic publication commit point
  last-good.json        # validated recovery reference
  .publication.lock     # same-host writer coordination
```

Candidate batches remain provisional. `accepted.json` is authoritative after a
generation is committed; `corpus.json` is derived from that exact accepted
snapshot. Raw pages and candidate files are not copied into the operational
root. A generation creation/publication time is backend metadata, never the
university source's effective date.

## Publication lifecycle and guarantee

`operational-import` performs this bounded local operation:

1. Validate every explicit course-description and syllabus candidate with the
   existing validators.
2. Acquire the same-host writer lock, read the committed generation, and merge
   by stable record identity.
3. Preserve unrelated records. Keep unchanged content and its version; assign
   version 1 to a new record; increment the version for changed content.
   Conflicting versions of one identity in the same operation are rejected.
4. Write a complete staging generation using same-directory temporary files,
   file flush/fsync, and `os.replace` after handles are closed.
5. Hash and validate accepted data, corpus, metadata, counts, generation links,
   and a fully constructed lexical retriever.
6. Move the immutable generation into `generations/`, preserve the prior
   manifest as `last-good.json`, then atomically replace `current.json`.
7. For in-process publication, load the committed generation and swap one
   process-local immutable retriever reference. In-flight requests retain their
   captured old retriever.

`current.json` is the only disk commit point. Readers therefore select all files
from the old generation or all files from the new generation. Two independent
replacements of accepted and corpus files are deliberately not used.

The code fsyncs file content and, on platforms that support it, parent directory
entries. On Windows, Python file `fsync` is used but directory fsync is not
available through this implementation. Atomic visibility and process-crash
recovery are tested; no stronger claim is made for power-loss durability on
every filesystem/storage device.

If failure happens before `current.json` replacement, the prior generation stays
current. An unreferenced completed or `.staging-*` generation is an orphan and
is never selected by directory scanning. If the durable manifest commit succeeds
but an in-process memory activation later fails, disk contains the new coherent
generation while that process may continue on its old coherent retriever; restart
loads the committed generation. That is not a disk rollback.

No historical generation is pruned automatically. Retention and redistribution
authorization remain team/data-owner decisions.

## Configuration and precedence

The operational root is ignored by Git and defaults to
`data/rag/operational/`. Set another persistent location before server startup
when needed:

```powershell
$env:RAG_OPERATIONAL_ROOT = "<persistent-writable-path>"
```

Path/mode precedence for an information request is:

1. an explicit in-process retriever (tests/internal calls);
2. an explicit `corpus_path` or CLI `--corpus` legacy override;
3. `RAG_OPERATIONAL_ROOT`, when configured;
4. `RAG_CORPUS_PATH`;
5. the legacy `data/rag/local-corpus.json` default.

An explicitly configured but empty/corrupt operational root returns an
actionable `corpus_unavailable` result. It does not silently select an unrelated
legacy corpus. Server configuration is captured by the process-local store;
restart after path changes.

## Safe import, inspection, and recovery

These commands perform no source or provider request. Run from the repository
root and use only candidate files already validated locally:

```powershell
python scripts/rag.py operational-import `
  --course-batch data/course_descriptions/candidates/<course-batch>.json `
  --syllabus-batch data/syllabi/candidates/<syllabus-batch>.json

python scripts/rag.py operational-inspect
```

Inspection omits source text and reports state, generation ID, record, document
and chunk counts, coverage, and accepted/corpus hashes. Reimporting only
unchanged content is idempotent and does not publish another generation.

Startup validates `current.json` and every referenced artifact. A corrupt
current generation may be served from a separately validated `last-good.json`;
inspection reports `recovered_last_good` and the backend logs a warning. Review
the damage first, then explicitly recommit the validated recovery reference:

```powershell
python scripts/rag.py operational-inspect
python scripts/rag.py operational-recover
python scripts/rag.py operational-inspect
```

`operational-recover` never chooses an arbitrary directory and fails if no valid
last-good reference exists. Do not manually edit manifests, hashes, or immutable
generation files.

For an offline answer after publication:

```powershell
$env:RAG_OPERATIONAL_ROOT = "data/rag/operational"
$env:RAG_GENERATION_MODE = "fallback"
python scripts/rag.py ask "What topics does COP4331 cover?" --course COP4331
```

The existing explicit `scripts/rag.py import --output ...` and `--corpus` demo
path remains available. It is a legacy, manually managed corpus path, not an
operational accepted/corpus transaction.

## Writer and reader model

Supported:

- one backend process on one host;
- persistent writable local filesystem;
- multiple request threads capturing immutable reader snapshots;
- one publication writer at a time;
- multiple same-host CLI/process writers serialized by the advisory lock.

In-process callers use the shared `RuntimeGenerationStore.publish` coordinator,
which swaps the retriever after disk commit and validation. A separate CLI
process safely updates disk while an API process is running, but it cannot hot
swap memory in that other process; the API keeps its old coherent generation
until restart. Out-of-process hot reload is not implemented.

Unsupported for acquisition enablement:

- ephemeral deployment storage;
- multiple backend workers with independent process caches;
- multiple hosts/replicas;
- a network filesystem whose rename/locking semantics are unknown.

The lock is same-host coordination, not a distributed lock. Unsupported
deployments must not claim safe live publication. Before acquisition is enabled,
the backend owner must answer whether deployment is one process/replica with a
persistent volume or requires shared storage and a cross-process reload design.

## Limits and next integration point

This prerequisite adds no endpoint, arbitrary-file upload, collector call,
background job, database, vector store, source cleanup, or answer cache. It does
not populate tracked `accepted.json` templates.

The next bounded acquisition task may connect an already eligible, resolved
catalog acquisition plan to collection **outside** the publication lock. After
collection and validation finish, it should call the same publication
coordinator with the resulting candidate path. Syllabus discovery and generic
automatic fetch-on-miss remain outside that increment.
