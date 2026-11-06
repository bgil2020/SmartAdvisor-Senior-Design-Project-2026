"""Atomic operational accepted/corpus generations for one persistent host.

The atomic commit point is ``current.json``. A manifest references one immutable
generation directory containing both the authoritative accepted snapshot and its
derived corpus. This module coordinates writers on one host; it is not a
distributed lock or a multi-replica publication protocol.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
import threading
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.course_descriptions.models import SCHEMA_VERSION, read_json, utc_now
from backend.course_descriptions.storage import validate_batch as validate_course_batch
from backend.course_descriptions.storage import validate_record as validate_course_record
from backend.syllabi.storage import validate_batch as validate_syllabus_batch
from backend.syllabi.storage import validate_record as validate_syllabus_record

from .corpus import CORPUS_VERSION, build_corpus, load_corpus
from .retriever import LexicalRetriever

OPERATIONAL_SCHEMA_VERSION = "1.0"
MANIFEST_NAME = "current.json"
LAST_GOOD_NAME = "last-good.json"
ACCEPTED_NAME = "accepted.json"
CORPUS_NAME = "corpus.json"
METADATA_NAME = "metadata.json"
LOGGER = logging.getLogger(__name__)


class OperationalStorageError(RuntimeError):
    """An operational generation could not be safely read or published."""


class WriterBusyError(OperationalStorageError):
    """Another supported writer currently owns the operational root."""


@dataclass(frozen=True)
class GenerationSnapshot:
    generation_id: str
    manifest: dict[str, Any]
    accepted: dict[str, Any]
    corpus: dict[str, Any]
    retriever: LexicalRetriever
    recovered_from_last_good: bool = False


@dataclass(frozen=True)
class PublicationResult:
    changed: bool
    generation_id: str
    accepted_record_count: int
    document_count: int
    chunk_count: int
    accepted_sha256: str
    corpus_sha256: str
    manifest_path: str
    retriever: LexicalRetriever


def default_operational_root(repository_root: Path) -> Path:
    configured = os.getenv("RAG_OPERATIONAL_ROOT")
    path = Path(configured) if configured else repository_root / "data" / "rag" / "operational"
    return path if path.is_absolute() else repository_root / path


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fsync_directory(path: Path) -> None:
    """Best-effort parent fsync on platforms that support directory handles."""
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _replace(source: Path, target: Path) -> None:
    os.replace(source, target)


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    """Durably write file content, then atomically replace one directory entry."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_json_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        _replace(temporary, path)
        _fsync_directory(path.parent)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


class _HostWriterLock:
    """Advisory same-host lock released by the OS when the process exits."""

    _process_locks_guard = threading.Lock()
    _process_locks: dict[str, threading.Lock] = {}

    def __init__(self, root: Path, timeout_seconds: float = 10.0):
        self.root = root
        self.timeout_seconds = timeout_seconds
        self.path = root / ".publication.lock"
        self.handle: Any = None
        key = str(root.resolve()).casefold()
        with self._process_locks_guard:
            self.process_lock = self._process_locks.setdefault(key, threading.Lock())

    def __enter__(self) -> "_HostWriterLock":
        if not self.process_lock.acquire(timeout=self.timeout_seconds):
            raise WriterBusyError("Timed out waiting for the in-process publication writer")
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            self.handle = self.path.open("a+b")
            self.handle.seek(0, os.SEEK_END)
            if self.handle.tell() == 0:
                self.handle.write(b"0")
                self.handle.flush()
            deadline = time.monotonic() + self.timeout_seconds
            while True:
                try:
                    self.handle.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError as exc:
                    if time.monotonic() >= deadline:
                        raise WriterBusyError("Timed out waiting for the same-host publication writer") from exc
                    time.sleep(0.05)
            return self
        except BaseException:
            if self.handle is not None:
                self.handle.close()
                self.handle = None
            self.process_lock.release()
            raise

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        try:
            if self.handle is not None:
                self.handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
                self.handle.close()
        finally:
            self.handle = None
            self.process_lock.release()


def _validate_operational_records(records: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for index, record in enumerate(records):
        category = record.get("record_category")
        if category == "course_description":
            errors = validate_course_record(record)
        elif category == "syllabus":
            errors = validate_syllabus_record(record)
        else:
            errors = [f"unsupported record_category: {category}"]
        if errors:
            raise OperationalStorageError(f"Invalid accepted record {index}: {errors}")
        record_id = record["record_id"]
        if record_id in seen:
            raise OperationalStorageError(f"Duplicate accepted record identity: {record_id}")
        seen.add(record_id)


def _load_candidates(course_batches: list[Path], syllabus_batches: list[Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    incoming: dict[str, dict[str, Any]] = {}
    inputs: list[dict[str, Any]] = []
    for category, paths, validator in (
        ("course_description", course_batches, validate_course_batch),
        ("syllabus", syllabus_batches, validate_syllabus_batch),
    ):
        for path in paths:
            batch = read_json(path)
            validation = validator(batch)
            if not validation["valid"]:
                raise OperationalStorageError(f"Invalid {category} candidate {path}: {validation['errors']}")
            for record in batch.get("records", []):
                current = incoming.get(record["record_id"])
                if current and current.get("content_sha256") != record.get("content_sha256"):
                    raise OperationalStorageError(f"Conflicting candidate content for {record['record_id']}")
                incoming.setdefault(record["record_id"], deepcopy(record))
            inputs.append({
                "category": category,
                "batch_id": batch.get("batch_id"),
                "record_count": len(batch.get("records", [])),
            })
    if not inputs:
        raise OperationalStorageError("At least one validated candidate batch is required")
    return list(incoming.values()), inputs


def _records_fingerprint(records: list[dict[str, Any]]) -> str:
    identity = [
        {
            "record_id": record["record_id"],
            "record_version": record["record_version"],
            "content_sha256": record["content_sha256"],
        }
        for record in sorted(records, key=lambda item: item["record_id"])
    ]
    return _sha256_bytes(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _merge_records(current: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    existing = {record["record_id"]: deepcopy(record) for record in current}
    changed = False
    for candidate in incoming:
        record_id = candidate["record_id"]
        prior = existing.get(record_id)
        if prior is None:
            updated = deepcopy(candidate)
            updated["record_version"] = 1
            existing[record_id] = updated
            changed = True
            continue
        if prior.get("record_category") != candidate.get("record_category"):
            raise OperationalStorageError(f"Incompatible category for existing identity {record_id}")
        if prior.get("content_sha256") == candidate.get("content_sha256"):
            continue
        updated = deepcopy(candidate)
        updated["record_version"] = int(prior["record_version"]) + 1
        existing[record_id] = updated
        changed = True
    merged = sorted(existing.values(), key=lambda item: item["record_id"])
    _validate_operational_records(merged)
    return merged, changed


def _generation_path(root: Path, generation_id: str) -> Path:
    if not generation_id or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_." for character in generation_id):
        raise OperationalStorageError("Manifest contains an unsafe generation ID")
    return root / "generations" / generation_id


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = read_json(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise OperationalStorageError(f"Cannot read publication manifest {path.name}: {type(exc).__name__}") from exc
    if manifest.get("operational_schema_version") != OPERATIONAL_SCHEMA_VERSION:
        raise OperationalStorageError("Unsupported operational manifest schema")
    return manifest


def _load_generation(root: Path, manifest: dict[str, Any], *, recovered: bool = False) -> GenerationSnapshot:
    generation_id = str(manifest.get("generation_id", ""))
    generation = _generation_path(root, generation_id)
    accepted_path = generation / ACCEPTED_NAME
    corpus_path = generation / CORPUS_NAME
    metadata_path = generation / METADATA_NAME
    for path, field in (
        (accepted_path, "accepted_sha256"),
        (corpus_path, "corpus_sha256"),
        (metadata_path, "metadata_sha256"),
    ):
        if not path.is_file():
            raise OperationalStorageError(f"Published generation is missing {path.name}")
        if _sha256_file(path) != manifest.get(field):
            raise OperationalStorageError(f"Published generation integrity mismatch for {path.name}")
    accepted = read_json(accepted_path)
    metadata = read_json(metadata_path)
    records = accepted.get("records")
    if accepted.get("operational_schema_version") != OPERATIONAL_SCHEMA_VERSION or not isinstance(records, list):
        raise OperationalStorageError("Malformed operational accepted snapshot")
    _validate_operational_records(records)
    corpus = load_corpus(corpus_path)
    if corpus.get("generation_id") != generation_id:
        raise OperationalStorageError("Corpus generation identity does not match manifest")
    if corpus.get("accepted_snapshot_sha256") != manifest.get("accepted_sha256"):
        raise OperationalStorageError("Corpus and accepted snapshot hashes do not match")
    if corpus.get("document_count") != len(records):
        raise OperationalStorageError("Corpus document count does not match accepted snapshot")
    if metadata.get("generation_id") != generation_id:
        raise OperationalStorageError("Metadata generation identity does not match manifest")
    if metadata.get("accepted_sha256") != manifest.get("accepted_sha256") or metadata.get("corpus_sha256") != manifest.get("corpus_sha256"):
        raise OperationalStorageError("Metadata artifact hashes do not match manifest")
    retriever = LexicalRetriever.from_path(corpus_path)
    return GenerationSnapshot(generation_id, manifest, accepted, corpus, retriever, recovered)


def load_current_generation(root: Path, *, allow_last_good: bool = True) -> GenerationSnapshot | None:
    """Load current, returning None only for a genuinely empty first-use root."""
    current = root / MANIFEST_NAME
    last_good = root / LAST_GOOD_NAME
    if not current.exists():
        if allow_last_good and last_good.exists():
            recovered = _load_generation(root, _read_manifest(last_good), recovered=True)
            LOGGER.warning("Operational current manifest is missing; serving validated last-good generation %s", recovered.generation_id)
            return recovered
        # Generation directories without a committed manifest are orphans. This
        # is expected if a first publication fails at its final commit point;
        # they are never selected implicitly.
        return None
    try:
        return _load_generation(root, _read_manifest(current))
    except OperationalStorageError as current_error:
        if allow_last_good and last_good.exists():
            try:
                recovered = _load_generation(root, _read_manifest(last_good), recovered=True)
                LOGGER.warning(
                    "Operational current generation is invalid; serving validated last-good generation %s until explicit recovery",
                    recovered.generation_id,
                )
                return recovered
            except OperationalStorageError as recovery_error:
                raise OperationalStorageError(f"Current generation is invalid and last-good recovery failed: {recovery_error}") from current_error
        raise


def recover_last_good(root: Path, *, lock_timeout_seconds: float = 10.0) -> dict[str, Any]:
    """Explicitly recommit a validated last-good manifest after current damage."""
    with _HostWriterLock(root, lock_timeout_seconds):
        try:
            current = load_current_generation(root, allow_last_good=False)
        except OperationalStorageError:
            current = None
        if current is not None:
            return {"changed": False, "generation_id": current.generation_id, "state": "current_already_valid"}
        last_good_path = root / LAST_GOOD_NAME
        if not last_good_path.exists():
            raise OperationalStorageError("No last-good manifest is available for explicit recovery")
        manifest = _read_manifest(last_good_path)
        recovered = _load_generation(root, manifest, recovered=True)
        _atomic_write_json(root / MANIFEST_NAME, manifest)
        return {"changed": True, "generation_id": recovered.generation_id, "state": "last_good_recommitted"}


def inspect_operational_storage(root: Path) -> dict[str, Any]:
    snapshot = load_current_generation(root)
    if snapshot is None:
        return {"state": "empty", "root": str(root), "current_generation": None}
    return {
        "state": "recovered_last_good" if snapshot.recovered_from_last_good else "ready",
        "root": str(root),
        "current_generation": snapshot.generation_id,
        "accepted_record_count": len(snapshot.accepted["records"]),
        "document_count": snapshot.corpus["document_count"],
        "chunk_count": snapshot.corpus["chunk_count"],
        "course_coverage": snapshot.corpus["course_coverage"],
        "syllabus_coverage": snapshot.corpus["syllabus_coverage"],
        "accepted_sha256": snapshot.manifest["accepted_sha256"],
        "corpus_sha256": snapshot.manifest["corpus_sha256"],
    }


def publish_candidates(
    root: Path,
    *,
    course_batches: list[Path],
    syllabus_batches: list[Path],
    lock_timeout_seconds: float = 10.0,
) -> PublicationResult:
    """Merge validated candidates and atomically publish one coherent generation."""
    incoming, inputs = _load_candidates(course_batches, syllabus_batches)
    with _HostWriterLock(root, lock_timeout_seconds):
        current = load_current_generation(root, allow_last_good=False)
        current_records = current.accepted["records"] if current else []
        merged, changed = _merge_records(current_records, incoming)
        if current is not None and not changed:
            return PublicationResult(
                False, current.generation_id, len(current_records), current.corpus["document_count"],
                current.corpus["chunk_count"], current.manifest["accepted_sha256"],
                current.manifest["corpus_sha256"], str(root / MANIFEST_NAME), current.retriever,
            )

        created_at = utc_now()
        fingerprint = _records_fingerprint(merged)
        generation_id = f"{created_at.replace(':', '').replace('-', '').replace('.', '')}-{fingerprint[:12]}"
        generations = root / "generations"
        generations.mkdir(parents=True, exist_ok=True)
        staging = generations / f".staging-{uuid.uuid4().hex}"
        final = _generation_path(root, generation_id)
        staging.mkdir()
        try:
            accepted = {
                "operational_schema_version": OPERATIONAL_SCHEMA_VERSION,
                "source_schema_version": SCHEMA_VERSION,
                "generation_id": generation_id,
                "created_at": created_at,
                "records_fingerprint": fingerprint,
                "inputs": inputs,
                "records": merged,
            }
            _atomic_write_json(staging / ACCEPTED_NAME, accepted)
            accepted_sha256 = _sha256_file(staging / ACCEPTED_NAME)
            corpus = build_corpus(
                merged,
                inputs=inputs,
                accepted_snapshot_sha256=accepted_sha256,
                generation_id=generation_id,
            )
            _atomic_write_json(staging / CORPUS_NAME, corpus)
            corpus_sha256 = _sha256_file(staging / CORPUS_NAME)
            metadata = {
                "operational_schema_version": OPERATIONAL_SCHEMA_VERSION,
                "source_schema_version": SCHEMA_VERSION,
                "corpus_schema_version": CORPUS_VERSION,
                "generation_id": generation_id,
                "created_at": created_at,
                "accepted_sha256": accepted_sha256,
                "corpus_sha256": corpus_sha256,
                "accepted_record_count": len(merged),
                "document_count": corpus["document_count"],
                "chunk_count": corpus["chunk_count"],
                "publication_time_meaning": "Backend generation creation time; not a university source effective date.",
            }
            _atomic_write_json(staging / METADATA_NAME, metadata)
            metadata_sha256 = _sha256_file(staging / METADATA_NAME)

            # Validate all hashes/contracts and construct the retriever before the
            # manifest can make the generation current.
            validation_manifest = {
                "operational_schema_version": OPERATIONAL_SCHEMA_VERSION,
                "generation_id": generation_id,
                "accepted_sha256": accepted_sha256,
                "corpus_sha256": corpus_sha256,
                "metadata_sha256": metadata_sha256,
                "published_at": None,
            }
            temporary_root = staging.parent.parent / f".validation-{uuid.uuid4().hex}"
            # Validation uses the final layout without publishing a manifest.
            temporary_generation = temporary_root / "generations" / generation_id
            temporary_generation.parent.mkdir(parents=True)
            _replace(staging, temporary_generation)
            try:
                prepared = _load_generation(temporary_root, validation_manifest)
                _replace(temporary_generation, final)
            finally:
                shutil.rmtree(temporary_root, ignore_errors=True)
            _fsync_directory(generations)

            manifest = {**validation_manifest, "published_at": utc_now()}
            if current is not None:
                _atomic_write_json(root / LAST_GOOD_NAME, current.manifest)
            _atomic_write_json(root / MANIFEST_NAME, manifest)
            if current is None:
                # Establish a recovery reference after (never before) the first
                # generation becomes current. Failure here does not undo or
                # invalidate the already committed current manifest.
                try:
                    _atomic_write_json(root / LAST_GOOD_NAME, manifest)
                except OSError:
                    pass
            return PublicationResult(
                True, generation_id, len(merged), corpus["document_count"], corpus["chunk_count"],
                accepted_sha256, corpus_sha256, str(root / MANIFEST_NAME), prepared.retriever,
            )
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise


class RuntimeGenerationStore:
    """Process-local immutable retriever reference backed by published generations."""

    def __init__(self, root: Path):
        self.root = root
        self._guard = threading.Lock()
        self._snapshot = load_current_generation(root)

    def snapshot(self) -> GenerationSnapshot | None:
        with self._guard:
            return self._snapshot

    def reload(self) -> GenerationSnapshot | None:
        loaded = load_current_generation(self.root)
        with self._guard:
            self._snapshot = loaded
            return self._snapshot

    def publish(self, *, course_batches: list[Path], syllabus_batches: list[Path]) -> PublicationResult:
        result = publish_candidates(self.root, course_batches=course_batches, syllabus_batches=syllabus_batches)
        # The durable commit has already succeeded. If process activation were to
        # fail, callers must report a runtime activation failure and restart; they
        # must not claim the disk publication rolled back.
        loaded = load_current_generation(self.root, allow_last_good=False)
        if loaded is None:
            raise OperationalStorageError("Published manifest disappeared before runtime activation")
        with self._guard:
            self._snapshot = loaded
        return result


_runtime_registry_guard = threading.Lock()
_runtime_registry: dict[str, RuntimeGenerationStore] = {}


def get_runtime_store(root: Path) -> RuntimeGenerationStore:
    key = str(root.resolve()).casefold()
    with _runtime_registry_guard:
        store = _runtime_registry.get(key)
        if store is None:
            store = RuntimeGenerationStore(root)
            _runtime_registry[key] = store
        return store


def clear_runtime_store_cache() -> None:
    """Test/server-lifecycle hook; does not modify disk state."""
    with _runtime_registry_guard:
        _runtime_registry.clear()
