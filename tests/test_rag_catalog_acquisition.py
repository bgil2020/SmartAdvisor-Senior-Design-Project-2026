"""Offline tests for the opt-in one-course catalog acquisition executor."""
from __future__ import annotations

import threading
import time
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

import backend.conversational_router as conversation_router
from backend.api import app
from backend.course_descriptions.models import SCHEMA_VERSION, write_json
from backend.course_descriptions.parser import parse_course_detail
from backend.rag.catalog_acquisition import (
    CatalogAcquisitionCoordinator,
    CatalogAcquisitionSettings,
    clear_catalog_acquisition_coordinators,
)
from backend.rag.models import AcquisitionPlan
from backend.rag.generation import BaseRAGProvider
from backend.rag.operational_storage import (
    RuntimeGenerationStore,
    clear_runtime_store_cache,
    get_runtime_store,
)
from backend.rag.service import answer_information_question

FIXTURE = Path(__file__).parent / "course_descriptions" / "fixtures" / "detail_full.html"
client = TestClient(app)


def html_for(course: str, description: str | None = None) -> str:
    value = FIXTURE.read_text(encoding="utf-8").replace("COP4331", course)
    if description:
        value = value.replace(
            "Introduces object-oriented analysis, design, implementation, and collaborative software development.",
            description,
        )
    return value


def record_for(course: str = "COP4331") -> dict:
    return parse_course_detail(
        html_for(course),
        expected_course_code=course,
        source_url=f"https://catalog.fau.edu/courses/{course}",
        fetched_at="2026-11-06T00:00:00Z",
        raw_evidence_ref="synthetic-test-fixture",
    )


def candidate(path: Path, batch_id: str, records: list[dict]) -> Path:
    write_json(path, {
        "schema_version": SCHEMA_VERSION,
        "batch_id": batch_id,
        "delivery_mode": "partial",
        "created_at": "2026-11-06T00:00:00Z",
        "source_manifest": "synthetic-test-fixture",
        "records": records,
        "outcomes": [],
        "limitations": ["Synthetic fixture; not university evidence."],
    })
    return path


def seeded_store(tmp_path: Path) -> RuntimeGenerationStore:
    store = RuntimeGenerationStore(tmp_path / "operational")
    store.publish(course_batches=[candidate(tmp_path / "seed.json", "fixture-seed", [record_for()])], syllabus_batches=[])
    return store


def plan(course: str = "CDA4102") -> AcquisitionPlan:
    return AcquisitionPlan(
        eligible=True,
        course_code=course,
        source_categories=["course_description"],
        evidence_gap="appropriate_source_absent",
        collector_capability="bounded fixture catalog",
    )


def sitemap(*courses: str) -> str:
    nodes = "".join(f"<url><loc>https://catalog.fau.edu/courses/{course}</loc></url>" for course in courses)
    return f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{nodes}</urlset>'


def coordinator(tmp_path: Path, handler, **overrides) -> CatalogAcquisitionCoordinator:
    values = {
        "enabled": True,
        "data_root": tmp_path / "acquisition",
        "request_timeout_seconds": 1.0,
        "total_deadline_seconds": 2.0,
        "pace_seconds": 0.0,
        "max_retries": 0,
        "max_retry_after_seconds": 0.0,
        "max_requests": 4,
        "max_response_bytes": 1024 * 1024,
        "max_redirects": 1,
        "max_concurrent": 1,
        "failure_cooldown_seconds": 30.0,
        "coordination_cache_size": 4,
    }
    values.update(overrides)
    settings = CatalogAcquisitionSettings(**values)
    return CatalogAcquisitionCoordinator(
        settings,
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )


def success_handler(course: str, calls: list[str], *, description: str | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=sitemap(course), request=request)
        return httpx.Response(200, text=html_for(course, description), request=request)
    return handler


def test_eligible_miss_collects_validates_publishes_activates_and_reuses(tmp_path):
    store = seeded_store(tmp_path)
    calls: list[str] = []
    executor = coordinator(tmp_path, success_handler("CDA4102", calls))

    first = executor.execute(plan(), runtime_store=store, supported_courses={"CDA4102"})
    assert first.outcome == "published"
    assert first.request_count == 2 and first.redirect_count == first.retry_count == 0
    assert first.source_url == "https://catalog.fau.edu/courses/CDA4102"
    assert store.snapshot() and store.snapshot().generation_id == first.generation_id
    ready = answer_information_question(
        "What topics does CDA4102 cover?",
        course_codes=["CDA4102"],
        retriever=store.snapshot().retriever,
    )
    assert ready.evidence_decision == "ready"

    second = executor.execute(plan(), runtime_store=store, supported_courses={"CDA4102"})
    assert second.outcome == "local_evidence_available"
    assert calls == ["/sitemap.xml", "/courses/CDA4102"]


def test_feature_disabled_ineligible_and_uninitialized_make_zero_requests(tmp_path):
    calls: list[str] = []
    store = seeded_store(tmp_path)
    settings = CatalogAcquisitionSettings(enabled=False, data_root=tmp_path / "acquisition")
    disabled = CatalogAcquisitionCoordinator(settings, client_factory=lambda: (_ for _ in ()).throw(AssertionError("network")))
    assert disabled.execute(plan(), runtime_store=store, supported_courses={"CDA4102"}).outcome == "disabled"

    enabled = coordinator(tmp_path, lambda request: calls.append(str(request.url)) or httpx.Response(500, request=request))
    ineligible = plan(); ineligible.eligible = False
    assert enabled.execute(ineligible, runtime_store=store, supported_courses={"CDA4102"}).outcome == "ineligible_plan"
    empty = RuntimeGenerationStore(tmp_path / "empty")
    assert enabled.execute(plan(), runtime_store=empty, supported_courses={"CDA4102"}).outcome == "storage_uninitialized"
    assert enabled.execute(plan(), runtime_store=store, supported_courses=set()).outcome == "unsupported_course"
    assert calls == []


def test_wrong_course_candidate_is_rejected_and_current_preserved(tmp_path):
    store = seeded_store(tmp_path)
    generation = store.snapshot().generation_id
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=sitemap("CDA4102"), request=request)
        return httpx.Response(200, text=html_for("COP4331"), request=request)

    result = coordinator(tmp_path, handler).execute(plan(), runtime_store=store, supported_courses={"CDA4102"})
    assert result.outcome == "candidate_rejected"
    assert store.snapshot().generation_id == generation


def test_outside_redirect_is_rejected_before_following(tmp_path):
    store = seeded_store(tmp_path)
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(302, headers={"Location": "https://evil.example/sitemap.xml"}, request=request)
        raise AssertionError("outside redirect was followed")

    result = coordinator(tmp_path, handler).execute(plan(), runtime_store=store, supported_courses={"CDA4102"})
    assert result.outcome == "source_rejected"
    assert calls == ["https://catalog.fau.edu/sitemap.xml"]


def test_response_size_request_budget_denial_timeout_and_discovery_failure(tmp_path):
    cases = []

    def oversized(request):
        return httpx.Response(200, content=b"x" * 2048, request=request)
    cases.append((oversized, {"max_response_bytes": 1024}, "response_too_large"))

    def denied(request):
        return httpx.Response(403, request=request)
    cases.append((denied, {}, "access_denied"))

    def timed_out(request):
        raise httpx.ReadTimeout("fixture timeout", request=request)
    cases.append((timed_out, {}, "temporarily_unavailable"))

    def malformed(request):
        return httpx.Response(200, text="not xml", request=request)
    cases.append((malformed, {}, "discovery_failure"))

    def exceeds_total_deadline(request):
        time.sleep(0.02)
        return httpx.Response(200, text=sitemap("CDA4102"), request=request)
    cases.append((exceeds_total_deadline, {"total_deadline_seconds": 0.01}, "timeout"))

    for index, (handler, overrides, expected) in enumerate(cases):
        case_root = tmp_path / str(index)
        store = seeded_store(case_root)
        result = coordinator(case_root, handler, **overrides).execute(plan(), runtime_store=store, supported_courses={"CDA4102"})
        assert result.outcome == expected

    budget_root = tmp_path / "budget"
    budget_store = seeded_store(budget_root)
    calls = []

    def redirected(request):
        calls.append(request.url.path)
        return httpx.Response(302, headers={"Location": "/again"}, request=request)

    budget = coordinator(budget_root, redirected, max_requests=2, max_redirects=5).execute(
        plan(), runtime_store=budget_store, supported_courses={"CDA4102"}
    )
    assert budget.outcome == "request_budget_exceeded"
    assert len(calls) == 2


def test_transient_discovery_retry_is_bounded_and_counted(tmp_path):
    store = seeded_store(tmp_path)
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if request.url.path == "/sitemap.xml" and calls == 1:
            return httpx.Response(503, request=request)
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=sitemap("CDA4102"), request=request)
        return httpx.Response(200, text=html_for("CDA4102"), request=request)

    result = coordinator(tmp_path, handler, max_retries=1).execute(
        plan(), runtime_store=store, supported_courses={"CDA4102"}
    )
    assert result.outcome == "published"
    assert (result.request_count, result.retry_count, calls) == (3, 1, 3)


def test_no_result_cooldown_is_temporary_and_cache_is_bounded(tmp_path):
    store = seeded_store(tmp_path)
    calls: list[str] = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, text=sitemap(), request=request)

    executor = coordinator(tmp_path, handler, coordination_cache_size=2)
    first = executor.execute(plan(), runtime_store=store, supported_courses={"CDA4102"})
    second = executor.execute(plan(), runtime_store=store, supported_courses={"CDA4102"})
    assert first.outcome == "source_not_found"
    assert second.outcome == "cooldown_active"
    assert calls == ["/sitemap.xml"]

    for course in ("CAP2751", "CDA3203"):
        executor.execute(plan(course), runtime_store=store, supported_courses={course})
    assert len(executor._cooldowns) == 2


def test_simultaneous_duplicate_requests_are_coalesced(tmp_path):
    store = seeded_store(tmp_path)
    detail_started = threading.Event()
    release_detail = threading.Event()
    calls: list[str] = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=sitemap("CDA4102"), request=request)
        detail_started.set()
        assert release_detail.wait(2)
        return httpx.Response(200, text=html_for("CDA4102"), request=request)

    executor = coordinator(tmp_path, handler)
    results = []
    first = threading.Thread(target=lambda: results.append(executor.execute(plan(), runtime_store=store, supported_courses={"CDA4102"})))
    second = threading.Thread(target=lambda: results.append(executor.execute(plan(), runtime_store=store, supported_courses={"CDA4102"})))
    first.start(); assert detail_started.wait(2); second.start(); release_detail.set()
    first.join(3); second.join(3)
    assert len(results) == 2
    assert {item.outcome for item in results} == {"published"}
    assert sorted(item.coalesced for item in results) == [False, True]
    assert calls == ["/sitemap.xml", "/courses/CDA4102"]


def test_cancellation_after_network_start_never_publishes(tmp_path):
    store = seeded_store(tmp_path)
    generation = store.snapshot().generation_id
    cancelled = threading.Event()

    def handler(request):
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=sitemap("CDA4102"), request=request)
        cancelled.set()
        return httpx.Response(200, text=html_for("CDA4102"), request=request)

    result = coordinator(tmp_path, handler).execute(
        plan(), runtime_store=store, supported_courses={"CDA4102"}, cancelled=cancelled
    )
    assert result.outcome == "cancelled"
    assert store.snapshot().generation_id == generation
    assert not any(chunk.course_code == "CDA4102" for chunk in store.snapshot().retriever.chunks)


def test_publication_failure_preserves_current_generation(tmp_path, monkeypatch):
    store = seeded_store(tmp_path)
    generation = store.snapshot().generation_id
    calls: list[str] = []
    executor = coordinator(tmp_path, success_handler("CDA4102", calls))
    monkeypatch.setattr(store, "publish", lambda **kwargs: (_ for _ in ()).throw(OSError("fixture publication failure")))
    result = executor.execute(plan(), runtime_store=store, supported_courses={"CDA4102"})
    assert result.outcome == "publication_failed"
    assert store.snapshot().generation_id == generation


def test_conversation_first_request_acquires_second_reuses_and_missing_detail_does_not_refetch(tmp_path, monkeypatch):
    operational = tmp_path / "operational"
    acquisition = tmp_path / "acquisition"
    monkeypatch.setenv("RAG_OPERATIONAL_ROOT", str(operational))
    monkeypatch.setenv("RAG_CATALOG_ACQUISITION_ROOT", str(acquisition))
    monkeypatch.setenv("RAG_CATALOG_ACQUISITION_ENABLED", "true")
    monkeypatch.setenv("RAG_GENERATION_MODE", "fallback")
    monkeypatch.setenv("CONVERSATIONAL_PARSER_MODE", "deterministic")
    clear_runtime_store_cache(); clear_catalog_acquisition_coordinators()
    store = get_runtime_store(operational)
    store.publish(course_batches=[candidate(tmp_path / "seed.json", "fixture-seed", [record_for()])], syllabus_batches=[])
    calls: list[str] = []
    executor = coordinator(tmp_path, success_handler("CDA4102", calls))
    monkeypatch.setattr(conversation_router, "get_catalog_acquisition_coordinator", lambda settings: executor)

    payload = {"message": "What topics does CDA4102 cover?", "course_code": "CDA4102"}
    first = client.post("/conversation", json=payload).json()
    assert first["status"] == "rag_answered"
    assert first["initial_evidence_decision"] == "appropriate_source_absent"
    assert first["initial_acquisition_plan"]["execute"] is False
    assert first["acquisition_outcome"] == "published"
    assert first["post_acquisition_evidence_decision"] == "ready"
    assert first["generation_source"] == "source_excerpt_fallback"
    assert first["active_corpus_generation"]
    assert first["rag_sources"][0]["url"] == "https://catalog.fau.edu/courses/CDA4102"

    count = len(calls)
    second = client.post("/conversation", json=payload).json()
    assert second["acquisition_outcome"] == "not_needed"
    assert len(calls) == count == 2

    detail = client.post("/conversation", json={"message": "Does CDA4102 cover quantum teleportation?", "course_code": "CDA4102"}).json()
    assert detail["evidence_decision"] == "requested_detail_not_located"
    assert detail["acquisition_outcome"] == "not_eligible"
    assert len(calls) == count


def test_successful_acquisition_can_remain_insufficient_and_provider_failure_falls_back(tmp_path, monkeypatch):
    class FailingProvider(BaseRAGProvider):
        model_id = "fixture-provider"

        def generate(self, question, evidence):
            raise TimeoutError("fixture provider timeout")

    operational = tmp_path / "operational"
    monkeypatch.setenv("RAG_OPERATIONAL_ROOT", str(operational))
    monkeypatch.setenv("RAG_CATALOG_ACQUISITION_ENABLED", "true")
    monkeypatch.setenv("RAG_GENERATION_MODE", "gemini")
    monkeypatch.setenv("CONVERSATIONAL_PARSER_MODE", "deterministic")
    clear_runtime_store_cache(); clear_catalog_acquisition_coordinators()
    store = get_runtime_store(operational)
    store.publish(course_batches=[candidate(tmp_path / "seed.json", "fixture-seed", [record_for()])], syllabus_batches=[])

    calls: list[str] = []
    executor = coordinator(tmp_path, success_handler("CDA4102", calls))
    monkeypatch.setattr(conversation_router, "get_catalog_acquisition_coordinator", lambda settings: executor)
    import backend.rag.service as rag_service
    monkeypatch.setattr(rag_service, "provider_from_environment", lambda: FailingProvider())

    unsupported_detail = client.post("/conversation", json={
        "message": "Does CDA4102 cover quantum teleportation?",
        "course_code": "CDA4102",
    }).json()
    assert unsupported_detail["acquisition_outcome"] == "published"
    assert unsupported_detail["initial_evidence_decision"] == "appropriate_source_absent"
    assert unsupported_detail["post_acquisition_evidence_decision"] == "requested_detail_not_located"
    assert unsupported_detail["status"] == "no_relevant_evidence"

    # A separate missing course is acquired, then provider failure preserves a
    # cited extractive answer rather than an unsupported generated claim.
    calls.clear()
    executor_two = coordinator(tmp_path / "second", success_handler("CDA3203", calls))
    monkeypatch.setattr(conversation_router, "get_catalog_acquisition_coordinator", lambda settings: executor_two)
    answered = client.post("/conversation", json={
        "message": "What topics does CDA3203 cover?",
        "course_code": "CDA3203",
    }).json()
    assert answered["acquisition_outcome"] == "published"
    assert answered["generation_source"] == "source_excerpt_fallback"
    assert answered["generation_fallback_reason"].endswith("(TimeoutError)")
    assert answered["supporting_source_ids"]


def test_clarification_and_scheduling_route_never_invoke_acquisition(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_CATALOG_ACQUISITION_ENABLED", "true")
    monkeypatch.setattr(
        conversation_router,
        "get_catalog_acquisition_coordinator",
        lambda settings: (_ for _ in ()).throw(AssertionError("acquisition should not run")),
    )
    conflict = client.post("/conversation", json={
        "message": "What topics does COP4331 cover?",
        "course_code": "CDA4102",
    })
    assert conflict.status_code == 200 and conflict.json()["status"] == "clarification"
    scheduling = client.post("/conversation", json={"message": "Do my classes overlap?"})
    assert scheduling.status_code == 200
    assert scheduling.json()["acquisition_attempted"] is False
