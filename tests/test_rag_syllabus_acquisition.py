"""Offline verification for exact-mapping syllabus fetch-on-miss."""
from __future__ import annotations

import threading
from pathlib import Path

from fastapi.testclient import TestClient

import backend.conversational_router as conversation_router
import backend.rag.syllabus_acquisition as syllabus_module
from backend.api import app
from backend.course_descriptions.models import SCHEMA_VERSION, write_json
from backend.course_descriptions.parser import parse_course_detail
from backend.rag.generation import BaseRAGProvider
from backend.rag.models import AcquisitionPlan
from backend.rag.operational_storage import RuntimeGenerationStore, clear_runtime_store_cache, get_runtime_store
from backend.rag.service import answer_information_question
from backend.rag.syllabus_acquisition import (
    SyllabusAcquisitionCoordinator,
    SyllabusAcquisitionSettings,
    clear_syllabus_acquisition_coordinators,
    resolve_exact_mapping,
    run_browser_subprocess,
)

COURSE_FIXTURE = Path(__file__).parent / "course_descriptions" / "fixtures" / "detail_full.html"
SYLLABUS_FIXTURE = Path(__file__).parent / "syllabi" / "fixtures" / "rendered_complete.html"
client = TestClient(app)


def course_record(course: str = "EEL3111") -> dict:
    html = COURSE_FIXTURE.read_text(encoding="utf-8").replace("COP4331", course)
    return parse_course_detail(
        html,
        expected_course_code=course,
        source_url=f"https://catalog.fau.edu/courses/{course}",
        fetched_at="2026-11-06T00:00:00Z",
        raw_evidence_ref="synthetic-test-fixture",
    )


def course_candidate(path: Path) -> Path:
    write_json(path, {
        "schema_version": SCHEMA_VERSION,
        "batch_id": "fixture-course-seed",
        "delivery_mode": "partial",
        "created_at": "2026-11-06T00:00:00Z",
        "source_manifest": "synthetic-test-fixture",
        "records": [course_record()],
        "outcomes": [],
        "limitations": ["Synthetic fixture."],
    })
    return path


def seeded_store(tmp_path: Path) -> RuntimeGenerationStore:
    store = RuntimeGenerationStore(tmp_path / "operational")
    store.publish(course_batches=[course_candidate(tmp_path / "seed.json")], syllabus_batches=[])
    return store


def syllabus_html(*, quiz_text: str = "Quizzes are 25 percent; the best five scores count.") -> str:
    html = SYLLABUS_FIXTURE.read_text(encoding="utf-8")
    html = html.replace("COP 4331-002 Object-Oriented Design &amp; Programming", "EEL 3111-001 Circuits 1")
    html = html.replace("Assessments and Grading", "Course Evaluation Method")
    html = html.replace("Projects 60%; examinations 40%.", quiz_text)
    return html


def plan(*, course: str = "EEL3111", term: str | None = "202608", section: str | None = "001") -> AcquisitionPlan:
    return AcquisitionPlan(
        eligible=True,
        course_code=course,
        source_categories=["syllabus"],
        term_id=term,
        section=section,
        evidence_gap="appropriate_source_absent",
        collector_capability="exact fixture syllabus mapping",
    )


def settings(tmp_path: Path, **overrides) -> SyllabusAcquisitionSettings:
    values = {
        "enabled": True,
        "data_root": tmp_path / "syllabus-acquisition",
        "chrome_path": tmp_path / "fixture-chrome",
        "total_deadline_seconds": 2.0,
        "browser_deadline_seconds": 1.0,
        "failure_cooldown_seconds": 30.0,
        "coordination_cache_size": 4,
    }
    values.update(overrides)
    return SyllabusAcquisitionSettings(**values)


def successful_runner(*, html: str | None = None, calls: list[str] | None = None):
    def run(mapping, *, batch_id, settings, cancelled):
        if calls is not None:
            calls.append(f"{mapping['course_code']}:{mapping['term_id']}:{mapping['section']}:{mapping['source_document_id']}")
        destination = settings.data_root / "raw" / batch_id / f"{mapping['source_document_id']}.html"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(html if html is not None else syllabus_html(), encoding="utf-8")
        return {
            "outcome": "collected",
            "probe": {
                "status": "anonymous_full_document",
                "stop_reason": "rendered_document_ready",
                "actual_observed_responses": 7,
                "essential_document_requests": 2,
            },
        }
    return run


def test_existing_syllabus_is_local_and_disabled_or_missing_scope_never_runs(tmp_path):
    store = seeded_store(tmp_path)
    calls: list[str] = []
    executor = SyllabusAcquisitionCoordinator(settings(tmp_path), browser_runner=successful_runner(calls=calls))
    first = executor.execute(plan(), runtime_store=store)
    assert first.outcome == "published"
    second = executor.execute(plan(), runtime_store=store)
    assert second.outcome == "local_evidence_available"
    assert len(calls) == 1

    disabled = SyllabusAcquisitionCoordinator(settings(tmp_path / "disabled", enabled=False), browser_runner=lambda *a, **k: (_ for _ in ()).throw(AssertionError("browser")))
    assert disabled.execute(plan(), runtime_store=seeded_store(tmp_path / "disabled")).outcome == "disabled"
    assert executor.execute(plan(term=None), runtime_store=store).outcome == "missing_required_scope"
    assert executor.execute(plan(section=None), runtime_store=store).outcome == "missing_required_scope"


def test_exact_mapping_only_and_denied_mapping_requires_manual_collection(tmp_path):
    store = seeded_store(tmp_path)
    executor = SyllabusAcquisitionCoordinator(settings(tmp_path), browser_runner=lambda *a, **k: (_ for _ in ()).throw(AssertionError("browser")))
    assert resolve_exact_mapping("EEL3111", "202608", "001")["source_document_id"] == "a4bh2nqsq"
    assert executor.execute(plan(course="EEL3111", term="202701", section="001"), runtime_store=store).outcome == "source_unresolved"
    denied = executor.execute(plan(course="COP4331", term="202608", section="002"), runtime_store=store)
    assert denied.outcome == "manual_collection_required"
    assert denied.document_id == "sb4d8l8wb"


def test_success_publishes_exact_identity_activates_and_answers(tmp_path):
    store = seeded_store(tmp_path)
    calls: list[str] = []
    executor = SyllabusAcquisitionCoordinator(settings(tmp_path), browser_runner=successful_runner(calls=calls))
    result = executor.execute(plan(), runtime_store=store)
    assert result.outcome == "published"
    assert result.document_id == "a4bh2nqsq"
    assert result.stop_reason == "rendered_document_ready"
    assert (result.browser_response_count, result.essential_request_count) == (7, 2)
    assert store.snapshot().generation_id == result.generation_id
    answer = answer_information_question(
        "How are quizzes graded?",
        course_codes=["EEL3111"], term_id="202608", section="001",
        retriever=store.snapshot().retriever,
    )
    assert answer.evidence_decision == "ready"
    assert answer.sources[0]["url"].startswith("https://fau.simplesyllabus.com/doc/a4bh2nqsq/")


def test_wrong_course_term_section_content_is_rejected(tmp_path):
    variants = {
        "course": syllabus_html().replace("EEL 3111-001", "COP 4331-001"),
        "section": syllabus_html().replace("EEL 3111-001", "EEL 3111-999"),
        "term": syllabus_html().replace("Fall 2026 1 Full Term", "Spring 2027"),
    }
    for name, html in variants.items():
        root = tmp_path / name
        store = seeded_store(root)
        generation = store.snapshot().generation_id
        result = SyllabusAcquisitionCoordinator(settings(root), browser_runner=successful_runner(html=html)).execute(plan(), runtime_store=store)
        assert result.outcome == "identity_mismatch"
        assert store.snapshot().generation_id == generation


def test_browser_denial_incomplete_unavailable_timeout_and_cooldown(tmp_path):
    outcomes = [
        ({"outcome": "not_collected", "probe": {"status": "generic_access_denied", "stop_reason": "essential_access_denied", "actual_observed_responses": 1, "essential_document_requests": 1}}, "access_denied"),
        ({"outcome": "not_collected", "probe": {"status": "javascript_shell_awaiting_render", "stop_reason": "event_stream_ended", "actual_observed_responses": 4, "essential_document_requests": 1}}, "incomplete_extraction"),
        ({"outcome": "browser_unavailable", "reason": "fixture browser absent"}, "browser_unavailable"),
        ({"outcome": "timeout", "reason": "fixture timeout"}, "timeout"),
    ]
    for index, (browser, expected) in enumerate(outcomes):
        root = tmp_path / str(index)
        store = seeded_store(root)
        calls = 0
        def runner(*args, **kwargs):
            nonlocal calls
            calls += 1
            return browser
        executor = SyllabusAcquisitionCoordinator(settings(root), browser_runner=runner)
        first = executor.execute(plan(), runtime_store=store)
        second = executor.execute(plan(), runtime_store=store)
        assert first.outcome == expected
        assert second.outcome == "cooldown_active"
        assert second.attempted is False
        assert second.browser_response_count == 0
        assert second.essential_request_count == 0
        assert second.stop_reason == "cooldown_active"
        assert calls == 1


def test_incomplete_shell_and_wrong_document_candidate_do_not_publish(tmp_path):
    store = seeded_store(tmp_path)
    generation = store.snapshot().generation_id
    incomplete = SyllabusAcquisitionCoordinator(
        settings(tmp_path),
        browser_runner=successful_runner(html="<html><body>JavaScript shell</body></html>"),
    ).execute(plan(), runtime_store=store)
    assert incomplete.outcome == "invalid_candidate"
    assert store.snapshot().generation_id == generation


def test_duplicate_exact_scope_coalesces(tmp_path):
    store = seeded_store(tmp_path)
    started, release = threading.Event(), threading.Event()
    calls = 0
    def runner(mapping, *, batch_id, settings, cancelled):
        nonlocal calls
        calls += 1
        started.set(); assert release.wait(2)
        return successful_runner()(mapping, batch_id=batch_id, settings=settings, cancelled=cancelled)
    executor = SyllabusAcquisitionCoordinator(settings(tmp_path), browser_runner=runner)
    results = []
    one = threading.Thread(target=lambda: results.append(executor.execute(plan(), runtime_store=store)))
    two = threading.Thread(target=lambda: results.append(executor.execute(plan(), runtime_store=store)))
    one.start(); assert started.wait(2); two.start(); release.set(); one.join(3); two.join(3)
    assert calls == 1 and len(results) == 2
    assert {item.outcome for item in results} == {"published"}
    assert sorted(item.coalesced for item in results) == [False, True]


def test_cancellation_and_publication_failure_preserve_generation(tmp_path, monkeypatch):
    store = seeded_store(tmp_path)
    generation = store.snapshot().generation_id
    cancelled = threading.Event(); cancelled.set()
    cancel_runner = lambda *a, **k: {"outcome": "cancelled", "reason": "fixture cancelled"}
    result = SyllabusAcquisitionCoordinator(settings(tmp_path), browser_runner=cancel_runner).execute(plan(), runtime_store=store, cancelled=cancelled)
    assert result.outcome == "cancelled"
    assert store.snapshot().generation_id == generation

    executor = SyllabusAcquisitionCoordinator(settings(tmp_path / "failure"), browser_runner=successful_runner())
    failure_store = seeded_store(tmp_path / "failure")
    prior = failure_store.snapshot().generation_id
    monkeypatch.setattr(failure_store, "publish", lambda **kwargs: (_ for _ in ()).throw(OSError("fixture publication failure")))
    failed = executor.execute(plan(), runtime_store=failure_store)
    assert failed.outcome == "publication_failed"
    assert failure_store.snapshot().generation_id == prior


def test_subprocess_cancellation_terminates_before_result(monkeypatch, tmp_path):
    class FakeProcess:
        pid = 12345
        returncode = None
        def poll(self): return self.returncode
        def wait(self, timeout=None): self.returncode = -1; return self.returncode
        def kill(self): self.returncode = -9
        def communicate(self): return ("", "")
    process = FakeProcess()
    monkeypatch.setattr(syllabus_module.subprocess, "Popen", lambda *a, **k: process)
    terminated = []
    def terminate(item):
        terminated.append(item.pid); item.returncode = -1
    monkeypatch.setattr(syllabus_module, "_terminate_process_tree", terminate)
    cancelled = threading.Event(); cancelled.set()
    result = run_browser_subprocess(resolve_exact_mapping("EEL3111", "202608", "001"), batch_id="fixture-cancel", settings=settings(tmp_path), cancelled=cancelled)
    assert result["outcome"] == "cancelled"
    assert terminated == [12345]


def test_conversation_success_repeat_no_refetch_and_existing_detail_gap(tmp_path, monkeypatch):
    operational = tmp_path / "operational"
    monkeypatch.setenv("RAG_OPERATIONAL_ROOT", str(operational))
    monkeypatch.setenv("RAG_SYLLABUS_ACQUISITION_ENABLED", "true")
    monkeypatch.setenv("RAG_GENERATION_MODE", "fallback")
    monkeypatch.setenv("CONVERSATIONAL_PARSER_MODE", "deterministic")
    clear_runtime_store_cache(); clear_syllabus_acquisition_coordinators()
    store = get_runtime_store(operational)
    store.publish(course_batches=[course_candidate(tmp_path / "seed.json")], syllabus_batches=[])
    calls: list[str] = []
    executor = SyllabusAcquisitionCoordinator(settings(tmp_path), browser_runner=successful_runner(calls=calls))
    monkeypatch.setattr(conversation_router, "get_syllabus_acquisition_coordinator", lambda value: executor)

    payload = {"message": "How are quizzes graded in EEL3111-001?", "course_code": "EEL3111", "term": "202608", "section": "001"}
    first = client.post("/conversation", json=payload).json()
    assert first["initial_evidence_decision"] == "appropriate_source_absent"
    assert first["acquisition_outcome"] == "published"
    assert first["acquisition_document_id"] == "a4bh2nqsq"
    assert first["post_acquisition_evidence_decision"] == "ready"
    assert first["generation_source"] == "source_excerpt_fallback"
    assert first["rag_sources"][0]["record_category"] == "syllabus"

    second = client.post("/conversation", json=payload).json()
    assert second["acquisition_outcome"] == "not_needed"
    assert len(calls) == 1

    gap = client.post("/conversation", json={"message": "What is the late-quiz policy?", "course_code": "EEL3111", "term": "202608", "section": "001"}).json()
    assert gap["evidence_decision"] == "requested_detail_not_located"
    assert gap["acquisition_attempted"] is False
    assert len(calls) == 1


def test_post_import_insufficient_and_provider_failure_preserves_cited_fallback(tmp_path, monkeypatch):
    class FailingProvider(BaseRAGProvider):
        model_id = "fixture-provider"
        def generate(self, question, evidence): raise TimeoutError("fixture")

    operational = tmp_path / "operational"
    monkeypatch.setenv("RAG_OPERATIONAL_ROOT", str(operational))
    monkeypatch.setenv("RAG_SYLLABUS_ACQUISITION_ENABLED", "true")
    monkeypatch.setenv("RAG_GENERATION_MODE", "gemini")
    clear_runtime_store_cache(); clear_syllabus_acquisition_coordinators()
    store = get_runtime_store(operational)
    store.publish(course_batches=[course_candidate(tmp_path / "seed.json")], syllabus_batches=[])
    executor = SyllabusAcquisitionCoordinator(settings(tmp_path), browser_runner=successful_runner())
    monkeypatch.setattr(conversation_router, "get_syllabus_acquisition_coordinator", lambda value: executor)
    import backend.rag.service as rag_service
    monkeypatch.setattr(rag_service, "provider_from_environment", lambda: FailingProvider())

    missing = client.post("/conversation", json={"message": "What is the late-quiz policy?", "course_code": "EEL3111", "term": "202608", "section": "001"}).json()
    assert missing["acquisition_outcome"] == "published"
    assert missing["post_acquisition_evidence_decision"] == "requested_detail_not_located"

    ready = client.post("/conversation", json={"message": "How are quizzes graded?", "course_code": "EEL3111", "term": "202608", "section": "001"}).json()
    assert ready["generation_source"] == "source_excerpt_fallback"
    assert ready["generation_fallback_reason"].endswith("(TimeoutError)")
    assert ready["supporting_source_ids"]


def test_missing_mapping_through_api_does_not_start_browser(tmp_path, monkeypatch):
    operational = tmp_path / "operational"
    monkeypatch.setenv("RAG_OPERATIONAL_ROOT", str(operational))
    monkeypatch.setenv("RAG_SYLLABUS_ACQUISITION_ENABLED", "true")
    clear_runtime_store_cache(); clear_syllabus_acquisition_coordinators()
    store = get_runtime_store(operational)
    store.publish(course_batches=[course_candidate(tmp_path / "seed.json")], syllabus_batches=[])
    executor = SyllabusAcquisitionCoordinator(settings(tmp_path), browser_runner=lambda *a, **k: (_ for _ in ()).throw(AssertionError("browser")))
    monkeypatch.setattr(conversation_router, "get_syllabus_acquisition_coordinator", lambda value: executor)
    response = client.post("/conversation", json={"message": "How are quizzes graded?", "course_code": "EEL3111", "term": "202701", "section": "001"}).json()
    assert response["acquisition_outcome"] == "source_unresolved"
    assert response["status"] == "no_relevant_evidence"
