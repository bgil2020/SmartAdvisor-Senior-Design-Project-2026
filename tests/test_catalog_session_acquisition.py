from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from backend.course_descriptions.runtime import acquire_exact_course_description
from backend.session_evidence import validate_session_records

FIXTURE = Path(__file__).parent / "course_descriptions" / "fixtures" / "detail_full.html"


def client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_exact_catalog_acquisition_returns_signed_session_record(monkeypatch):
    monkeypatch.setenv("CATALOG_ACQUISITION_ENABLED", "true")
    monkeypatch.setenv("SESSION_EVIDENCE_SIGNING_KEY", "catalog-session-test-key-at-least-32-bytes")
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, text=FIXTURE.read_text(encoding="utf-8"), request=request)

    result = acquire_exact_course_description("COP4331", client=client_for(handler))
    assert result["status"] == "acquired"
    assert calls == ["https://catalog.fau.edu/courses/COP4331"]
    valid, errors = validate_session_records([result["record"]])
    assert errors == [] and valid[0]["record_category"] == "course_description"


def test_catalog_acquisition_denial_and_document_bound(monkeypatch):
    monkeypatch.setenv("CATALOG_ACQUISITION_ENABLED", "true")
    denied = acquire_exact_course_description(
        "COP4331",
        client=client_for(lambda request: httpx.Response(403, request=request)),
    )
    assert denied["status"] == "access_denied"

    monkeypatch.setenv("CATALOG_ACQUISITION_MAX_BYTES", "1024")
    oversized = acquire_exact_course_description(
        "COP4331",
        client=client_for(lambda request: httpx.Response(200, content=b"x" * 2048, request=request)),
    )
    assert oversized["status"] == "response_too_large"

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture timeout", request=request)

    timed_out = acquire_exact_course_description("COP4331", client=client_for(timeout))
    assert timed_out["status"] == "timeout"

    incomplete = acquire_exact_course_description(
        "COP4331",
        client=client_for(lambda request: httpx.Response(200, text="<html><title>Catalog</title></html>", request=request)),
    )
    assert incomplete["status"] == "candidate_rejected"


def test_catalog_acquisition_is_deduplicated(monkeypatch):
    monkeypatch.setenv("CATALOG_ACQUISITION_ENABLED", "true")
    monkeypatch.setenv("SESSION_EVIDENCE_SIGNING_KEY", "catalog-session-test-key-at-least-32-bytes")
    calls = 0
    lock = threading.Lock()

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        with lock:
            calls += 1
        time.sleep(0.1)
        return httpx.Response(200, text=FIXTURE.read_text(encoding="utf-8"), request=request)

    client = client_for(handler)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: acquire_exact_course_description("COP4331", client=client), range(2)))
    client.close()
    assert calls == 1
    assert [result["status"] for result in results] == ["acquired", "acquired"]
    assert sum(result.get("request_count", 0) for result in results) == 1
