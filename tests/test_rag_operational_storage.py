"""Offline failure-injection tests for atomic RAG generation publication."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from copy import deepcopy
from pathlib import Path

import pytest

from backend.course_descriptions.models import SCHEMA_VERSION, sha256_text, write_json
from backend.course_descriptions.parser import parse_course_detail
from backend.rag.operational_storage import (
    ACCEPTED_NAME,
    CORPUS_NAME,
    LAST_GOOD_NAME,
    MANIFEST_NAME,
    OperationalStorageError,
    RuntimeGenerationStore,
    inspect_operational_storage,
    load_current_generation,
    publish_candidates,
    recover_last_good,
)
from backend.rag.service import answer_information_question

FIXTURE = Path(__file__).parent / "course_descriptions" / "fixtures" / "detail_full.html"


def course_record(code: str = "COP4331") -> dict:
    html = FIXTURE.read_text(encoding="utf-8").replace("COP4331", code)
    return parse_course_detail(
        html,
        expected_course_code=code,
        source_url=f"https://catalog.fau.edu/courses/{code}",
        fetched_at="2026-11-01T00:00:00Z",
        raw_evidence_ref="synthetic-test-fixture",
    )


def changed_record(record: dict, phrase: str = " Includes a bounded fixture update.") -> dict:
    updated = deepcopy(record)
    updated["description"] += phrase
    updated["exact_source_text"] += phrase
    updated["content_sha256"] = sha256_text("\n".join([
        updated["course_code"], updated["title"], updated["description"], updated["prerequisite_text"]
    ]))
    return updated


def candidate(path: Path, batch_id: str, records: list[dict]) -> Path:
    write_json(path, {
        "schema_version": SCHEMA_VERSION,
        "batch_id": batch_id,
        "delivery_mode": "partial",
        "created_at": "2026-11-01T00:00:00Z",
        "source_manifest": "synthetic-test-fixture",
        "records": records,
        "outcomes": [],
        "limitations": ["Synthetic fixture; not source evidence."],
    })
    return path


def publish(root: Path, path: Path):
    return publish_candidates(root, course_batches=[path], syllabus_batches=[])


def test_empty_store_is_distinct_from_corrupt_storage(tmp_path):
    root = tmp_path / "operational"
    assert load_current_generation(root) is None
    assert inspect_operational_storage(root)["state"] == "empty"
    root.mkdir()
    (root / MANIFEST_NAME).write_text("not-json", encoding="utf-8")
    with pytest.raises(OperationalStorageError, match="Cannot read publication manifest"):
        load_current_generation(root)


def test_valid_candidate_initializes_coherent_generation_and_inspection(tmp_path):
    root = tmp_path / "operational"
    result = publish(root, candidate(tmp_path / "one.json", "fixture-one", [course_record()]))
    snapshot = load_current_generation(root)
    assert result.changed is True
    assert snapshot and snapshot.generation_id == result.generation_id
    assert snapshot.corpus["accepted_snapshot_sha256"] == result.accepted_sha256
    assert len(snapshot.accepted["records"]) == snapshot.corpus["document_count"] == 1
    assert (root / LAST_GOOD_NAME).is_file()
    assert inspect_operational_storage(root)["chunk_count"] == 2


def test_existing_records_preserved_and_two_supported_writers_do_not_lose_updates(tmp_path):
    root = tmp_path / "operational"
    first = candidate(tmp_path / "cop.json", "fixture-cop", [course_record("COP4331")])
    second = candidate(tmp_path / "cda.json", "fixture-cda", [course_record("CDA4102")])
    barrier = threading.Barrier(3)
    errors: list[BaseException] = []

    def worker(path: Path) -> None:
        try:
            barrier.wait()
            publish(root, path)
        except BaseException as exc:  # retained and asserted below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(path,)) for path in (first, second)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()
    assert not errors
    snapshot = load_current_generation(root)
    assert snapshot
    assert {item["course_code"] for item in snapshot.accepted["records"]} == {"COP4331", "CDA4102"}


def test_unchanged_content_is_idempotent_and_updated_content_versions(tmp_path):
    root = tmp_path / "operational"
    original = course_record()
    one = publish(root, candidate(tmp_path / "one.json", "fixture-one", [original]))
    duplicate = deepcopy(original)
    duplicate["fetched_at"] = "2026-11-02T00:00:00Z"
    same = publish(root, candidate(tmp_path / "same.json", "fixture-same", [duplicate]))
    assert same.changed is False
    assert same.generation_id == one.generation_id

    updated = publish(root, candidate(tmp_path / "updated.json", "fixture-updated", [changed_record(original)]))
    snapshot = load_current_generation(root)
    assert updated.changed is True and updated.generation_id != one.generation_id
    assert snapshot and snapshot.accepted["records"][0]["record_version"] == 2


def test_invalid_and_conflicting_candidates_are_rejected_before_publication(tmp_path):
    root = tmp_path / "operational"
    invalid = course_record()
    invalid["course_code"] = "not-a-course"
    with pytest.raises(OperationalStorageError, match="Invalid course_description candidate"):
        publish(root, candidate(tmp_path / "invalid.json", "fixture-invalid", [invalid]))
    assert load_current_generation(root) is None

    original = course_record()
    first = candidate(tmp_path / "first.json", "fixture-first", [original])
    second = candidate(tmp_path / "second.json", "fixture-second", [changed_record(original)])
    with pytest.raises(OperationalStorageError, match="Conflicting candidate content"):
        publish_candidates(root, course_batches=[first, second], syllabus_batches=[])
    assert load_current_generation(root) is None


@pytest.mark.parametrize("failure", ["accepted", "corpus"])
def test_generation_file_failure_leaves_no_current_and_releases_lock(tmp_path, monkeypatch, failure):
    import backend.rag.operational_storage as storage

    root = tmp_path / "operational"
    batch = candidate(tmp_path / "one.json", "fixture-one", [course_record()])
    real_write = storage._atomic_write_json

    def fail_selected(path, value):
        if path.name == (ACCEPTED_NAME if failure == "accepted" else CORPUS_NAME):
            raise OSError(f"injected {failure} write failure")
        return real_write(path, value)

    monkeypatch.setattr(storage, "_atomic_write_json", fail_selected)
    with pytest.raises(OSError, match="injected"):
        publish(root, batch)
    assert load_current_generation(root) is None
    monkeypatch.setattr(storage, "_atomic_write_json", real_write)
    assert publish(root, batch).changed is True


def test_failure_before_manifest_and_at_manifest_replace_never_selects_orphan(tmp_path, monkeypatch):
    import backend.rag.operational_storage as storage

    batch = candidate(tmp_path / "one.json", "fixture-one", [course_record()])
    for mode in ("before_manifest", "manifest_replace"):
        root = tmp_path / mode
        real_replace = storage._replace

        def injected(source, target):
            if mode == "before_manifest" and target.parent.name == "generations" and not target.name.startswith(".staging-"):
                raise OSError("injected final generation move failure")
            if mode == "manifest_replace" and target == root / MANIFEST_NAME:
                raise OSError("injected manifest replace failure")
            return real_replace(source, target)

        monkeypatch.setattr(storage, "_replace", injected)
        with pytest.raises(OSError, match="injected"):
            publish(root, batch)
        assert load_current_generation(root) is None
        monkeypatch.setattr(storage, "_replace", real_replace)


def test_failed_update_preserves_current_and_last_good(tmp_path, monkeypatch):
    import backend.rag.operational_storage as storage

    root = tmp_path / "operational"
    original = course_record()
    first = publish(root, candidate(tmp_path / "one.json", "fixture-one", [original]))
    updated = candidate(tmp_path / "two.json", "fixture-two", [changed_record(original)])
    real_replace = storage._replace

    def fail_current(source, target):
        if target == root / MANIFEST_NAME:
            raise PermissionError("injected current replacement denial")
        return real_replace(source, target)

    monkeypatch.setattr(storage, "_replace", fail_current)
    with pytest.raises(PermissionError, match="injected"):
        publish(root, updated)
    snapshot = load_current_generation(root)
    assert snapshot and snapshot.generation_id == first.generation_id


def test_reader_snapshots_are_coherent_and_inflight_reader_keeps_old_generation(tmp_path):
    root = tmp_path / "operational"
    original = course_record()
    first = candidate(tmp_path / "one.json", "fixture-one", [original])
    runtime = RuntimeGenerationStore(root)
    runtime.publish(course_batches=[first], syllabus_batches=[])
    old = runtime.snapshot()
    assert old
    runtime.publish(
        course_batches=[candidate(tmp_path / "two.json", "fixture-two", [changed_record(original)])],
        syllabus_batches=[],
    )
    new = runtime.snapshot()
    assert new and new.generation_id != old.generation_id
    assert old.retriever.search("collaborative software development", course_codes=["COP4331"])
    assert not old.retriever.search("bounded fixture update", course_codes=["COP4331"])
    assert new.retriever.search("bounded fixture update", course_codes=["COP4331"])


def test_restart_loads_committed_generation_and_service_uses_operational_mode(tmp_path, monkeypatch):
    root = tmp_path / "operational"
    result = publish(root, candidate(tmp_path / "one.json", "fixture-one", [course_record()]))
    restarted = RuntimeGenerationStore(root)
    assert restarted.snapshot() and restarted.snapshot().generation_id == result.generation_id
    monkeypatch.setenv("RAG_OPERATIONAL_ROOT", str(root))
    monkeypatch.setenv("RAG_GENERATION_MODE", "fallback")
    from backend.rag.operational_storage import clear_runtime_store_cache
    clear_runtime_store_cache()
    answer = answer_information_question("What topics does COP4331 cover?", course_codes=["COP4331"])
    assert answer.evidence_decision == "ready"

    environment = os.environ.copy()
    environment["RAG_OPERATIONAL_ROOT"] = str(root)
    environment["RAG_GENERATION_MODE"] = "fallback"
    completed = subprocess.run(
        [sys.executable, "scripts/rag.py", "ask", "What topics does COP4331 cover?", "--course", "COP4331"],
        cwd=Path(__file__).parents[1],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["evidence_decision"] == "ready"


def test_integrity_mismatch_and_missing_generation_are_actionable(tmp_path):
    root = tmp_path / "operational"
    publish(root, candidate(tmp_path / "one.json", "fixture-one", [course_record()]))
    manifest = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
    corpus = root / "generations" / manifest["generation_id"] / CORPUS_NAME
    corpus.write_text("{}", encoding="utf-8")
    with pytest.raises(OperationalStorageError, match="last-good recovery failed"):
        load_current_generation(root)

    other = tmp_path / "missing"
    publish(other, candidate(tmp_path / "other.json", "fixture-other", [course_record()]))
    missing_manifest = json.loads((other / MANIFEST_NAME).read_text(encoding="utf-8"))
    missing_manifest["generation_id"] = "does-not-exist"
    write_json(other / MANIFEST_NAME, missing_manifest)
    with pytest.raises(OperationalStorageError, match="missing accepted.json"):
        load_current_generation(other, allow_last_good=False)


def test_last_good_recovery_and_orphan_staging_ignored(tmp_path):
    root = tmp_path / "operational"
    original = course_record()
    first = publish(root, candidate(tmp_path / "one.json", "fixture-one", [original]))
    second = publish(root, candidate(tmp_path / "two.json", "fixture-two", [changed_record(original)]))
    orphan = root / "generations" / ".staging-unpublished"
    orphan.mkdir()
    current_manifest = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
    current_corpus = root / "generations" / current_manifest["generation_id"] / CORPUS_NAME
    current_corpus.write_text("corrupt", encoding="utf-8")
    recovered = load_current_generation(root)
    assert recovered and recovered.recovered_from_last_good is True
    assert recovered.generation_id == first.generation_id != second.generation_id
    result = recover_last_good(root)
    assert result == {"changed": True, "generation_id": first.generation_id, "state": "last_good_recommitted"}
    committed = load_current_generation(root, allow_last_good=False)
    assert committed and committed.generation_id == first.generation_id


def test_no_source_content_is_written_outside_ignored_operational_root(tmp_path):
    root = tmp_path / "operational"
    publish(root, candidate(tmp_path / "one.json", "fixture-one", [course_record()]))
    assert {path.relative_to(root).parts[0] for path in root.iterdir()} <= {
        "generations", MANIFEST_NAME, LAST_GOOD_NAME, ".publication.lock"
    }
