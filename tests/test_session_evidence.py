from pathlib import Path
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

os.environ["CONVERSATIONAL_PARSER_MODE"] = "deterministic"

from backend.conversational_router import ConversationRequest, handle_conversation
from backend.session_evidence import attach_provenance, validate_session_records
from backend.syllabi.models import stable_syllabus_id, syllabus_content_hash
from backend.syllabi.parser import parse_rendered_syllabus


FIXTURE = Path(__file__).parent / "syllabi" / "fixtures" / "rendered_complete.html"


def record(section: str = "002", source_id: str = "sb4d8l8wb") -> dict:
    parsed = parse_rendered_syllabus(
        FIXTURE.read_text(encoding="utf-8"), course_code="COP4331", term_id="202608",
        term_name="Fall 2026 1 Full Term", section=section, source_document_id=source_id,
        source_url=f"https://fau.simplesyllabus.com/doc/{source_id}/COP-4331?mode=view",
        fetched_at="2026-11-08T00:00:00Z", raw_evidence_ref="session-memory:test",
    )
    return attach_provenance(parsed)


def ask(message: str, evidence: list[dict], context: dict | None = None) -> dict:
    response = handle_conversation(ConversationRequest(message=message, session_evidence=evidence, session_context=context))
    return response.model_dump()


def test_reuses_exact_session_syllabus_with_zero_acquisition_and_citations():
    evidence = [record()]
    first = ask("What does the grading section say for COP 4331?", evidence, {"course_code": "COP4331", "term_id": "202608", "section": "002"})
    assert first["status"] == "grounded_answer"
    assert first["acquisition"]["additional_source_acquisitions"] == 0
    assert first["citations"]
    follow_up = ask("What are the learning outcomes for that class?", evidence, first["source_scope"])
    assert follow_up["status"] == "grounded_answer"
    assert follow_up["acquisition"]["additional_source_acquisitions"] == 0
    assert follow_up["source_scope"] == {"course_code": "COP4331", "term_id": "202608", "section": "002"}


def test_missing_information_does_not_refetch_loop():
    data = ask("What does the COP 4331 syllabus say about the cafeteria menu?", [record()], {"course_code": "COP4331", "term_id": "202608", "section": "002"})
    assert data["status"] == "grounded_answer"
    assert data["response_code"] == "SESSION_EVIDENCE_INSUFFICIENT"
    assert data["acquisition"]["additional_source_acquisitions"] == 0
    assert "did not refetch" in data["response_text"]


def test_tampered_client_verification_is_rejected():
    tampered = record()
    tampered["document_text"] = "invented"
    valid, errors = validate_session_records([tampered])
    assert not valid
    assert any("content_sha256" in item or "provenance" in item for item in errors)


def test_contextual_reference_with_multiple_sections_requires_clarification():
    second = {key: value for key, value in record().items() if key != "session_provenance"}
    second["section_scope"] = {"section": "003"}
    second["source"] = {**second["source"], "source_id": "anotherdoc", "url": "https://fau.simplesyllabus.com/doc/anotherdoc/COP-4331?mode=view"}
    second["record_id"] = stable_syllabus_id("COP4331", "202608", "003", "anotherdoc")
    second["content_sha256"] = syllabus_content_hash(second)
    second = attach_provenance(second)
    data = ask("What does that class say about grading?", [record(), second])
    assert data["status"] == "clarification"
    assert data["response_code"] == "SOURCE_SCOPE_AMBIGUOUS"


def test_record_count_limit_is_rejected_without_partial_trust():
    valid, errors = validate_session_records([record()] * 7)
    assert valid == []
    assert "record limit exceeded" in errors[0]


def test_stable_backend_key_allows_browser_evidence_after_restart(monkeypatch):
    monkeypatch.setenv("SESSION_EVIDENCE_SIGNING_KEY", "test-only-stable-key-with-sufficient-length")
    retained = record()
    # Revalidation uses only the configured backend secret and retained browser record;
    # it does not depend on an in-process server corpus.
    valid, errors = validate_session_records([retained])
    assert errors == []
    assert valid[0]["record_id"] == retained["record_id"]


def test_oversized_record_is_rejected_before_trust():
    oversized = record()
    oversized["document_text"] = "x" * 121_000
    valid, errors = validate_session_records([oversized])
    assert valid == []
    assert "per-record byte limit" in errors[0]


def test_concurrent_exact_acquisition_is_deduplicated(monkeypatch):
    from backend.syllabi import runtime

    monkeypatch.setenv("SYLLABUS_ACQUISITION_ENABLED", "true")
    monkeypatch.setenv("ACQUISITION_BROWSER_MODE", "headed")
    monkeypatch.setattr(runtime, "_mapping", lambda *_args: {"view_url": "https://fau.simplesyllabus.com/doc/test/exact"})
    calls = 0
    call_lock = threading.Lock()

    def fake_run(_mapping):
        nonlocal calls
        with call_lock:
            calls += 1
        time.sleep(0.1)
        return {"status": "generic_access_denied", "record": None, "duration_ms": 100, "cleanup": "attempted"}

    monkeypatch.setattr(runtime, "_run_mapping", fake_run)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: runtime.acquire_exact_syllabus("COP4331", "202608", "002"), range(2)))
    assert calls == 1
    assert [item["status"] for item in results] == ["generic_access_denied", "generic_access_denied"]
