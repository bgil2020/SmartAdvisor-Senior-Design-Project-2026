from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
import httpx

from backend.course_descriptions.models import SCHEMA_VERSION, read_json, stable_record_id, write_json
from backend.course_descriptions.fetcher import FetchConfig, fetch_courses
from backend.course_descriptions.parser import ParseError, parse_course_detail
from backend.course_descriptions.storage import accept_batch, compare_batches, rollback_accepted, validate_batch

FIXTURES = Path(__file__).parent / "course_descriptions" / "fixtures"


def parse_fixture(name: str = "detail_full.html", expected: str = "COP4331") -> dict:
    text = (FIXTURES / name).read_text(encoding="utf-8")
    return parse_course_detail(
        text,
        expected_course_code=expected,
        source_url=f"https://catalog.fau.edu/courses/{expected}",
        fetched_at="2026-10-30T12:00:00Z",
        raw_evidence_ref=f"tests/course_descriptions/fixtures/{name}",
    )


def batch(batch_id: str, records: list[dict], outcomes: list[dict] | None = None) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "batch_id": batch_id,
        "delivery_mode": "partial",
        "created_at": "2026-10-30T12:00:00Z",
        "source_manifest": "data/course_descriptions/sample-manifest.json",
        "records": records,
        "outcomes": outcomes or [],
        "limitations": ["partial"],
    }


def accepted(records: list[dict], batch_id: str = "accepted-v1") -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": "smartadvisor-course-descriptions",
        "accepted_batch_id": batch_id,
        "accepted_at": "2026-10-30T12:00:00Z",
        "previous_accepted_batch_id": None,
        "records": records,
    }


def test_extracts_full_description_and_separate_prerequisite():
    record = parse_fixture()
    assert record["course_code"] == "COP4331"
    assert record["title"] == "Object-Oriented Design and Programming"
    assert record["description"] == "Introduces object-oriented analysis, design, implementation, and collaborative software development."
    assert record["prerequisite_text"] == "Prerequisite: COP 3530C with minimum grade of C"
    assert record["exact_source_text"].startswith("Object-Oriented Design and Programming")


@pytest.mark.parametrize(
    ("fixture", "expected", "code"),
    [
        ("listing_truncated.html", "COP4331", "course_identity_mismatch"),
        ("detail_mismatch.html", "COP4331", "course_identity_mismatch"),
        ("detail_missing.html", "COP4331", "missing_description"),
        ("detail_ambiguous.html", "COP4331", "ambiguous_description"),
    ],
)
def test_rejects_non_detail_mismatch_missing_and_ambiguous_text(fixture, expected, code):
    with pytest.raises(ParseError) as caught:
        parse_fixture(fixture, expected)
    assert caught.value.code == code


def test_stable_id_is_content_independent_and_duplicate_is_invalid():
    first = parse_fixture()
    changed = deepcopy(first)
    changed["description"] = "Different source text."
    assert stable_record_id("COP 4331") == first["record_id"] == changed["record_id"]
    result = validate_batch(batch("duplicate", [first, deepcopy(first)]))
    assert result["valid"] is False
    assert any("duplicate record ID" in item["message"] for item in result["errors"])


def test_compare_ignores_timestamp_only_changes():
    first = parse_fixture()
    later = deepcopy(first)
    later["fetched_at"] = "2026-11-01T00:00:00Z"
    diff = compare_batches(accepted([first]), batch("candidate", [later]))
    assert diff["unchanged"] == [first["record_id"]]
    assert diff["changed"] == []


def test_compare_distinguishes_content_and_outcomes():
    first = parse_fixture()
    changed = deepcopy(first)
    changed["description"] += " New exact sentence."
    from backend.course_descriptions.models import sha256_text
    changed["content_sha256"] = sha256_text("\n".join([changed["course_code"], changed["title"], changed["description"], changed["prerequisite_text"]]))
    diff = compare_batches(
        accepted([first]),
        batch("candidate", [changed], [{"course_code": "EEL3111", "status": "failed"}, {"course_code": "CAP4773", "status": "not_found"}, {"course_code": "CDA4102", "status": "ambiguous"}]),
    )
    assert diff["changed"] == [first["record_id"]]
    assert diff["failed"] == ["EEL3111"]
    assert diff["not_found"] == ["CAP4773"]
    assert diff["ambiguous"] == ["CDA4102"]


def test_partial_omission_and_failed_fetch_do_not_delete_accepted(tmp_path):
    first = parse_fixture()
    other = deepcopy(first)
    other["course_code"] = "CDA4102"
    other["record_id"] = stable_record_id("CDA4102")
    other["course_scope"] = {"course_code": "CDA4102"}
    other["source"]["url"] = "https://catalog.fau.edu/courses/CDA4102"
    other["title"] = "Computer Architecture"
    other["description"] = "Studies computer architecture."
    other["exact_source_text"] = other["description"]
    from backend.course_descriptions.models import sha256_text
    other["content_sha256"] = sha256_text("\n".join([other["course_code"], other["title"], other["description"], other["prerequisite_text"]]))
    accepted_path = tmp_path / "accepted.json"
    candidate_path = tmp_path / "candidate.json"
    write_json(accepted_path, accepted([first, other]))
    write_json(candidate_path, batch("partial", [first], [{"course_code": "CDA4102", "status": "failed"}]))
    result = accept_batch(candidate_path, accepted_path, tmp_path / "history")
    assert result["record_count"] == 2
    assert {item["record_id"] for item in read_json(accepted_path)["records"]} == {first["record_id"], other["record_id"]}


def test_repeated_accept_is_idempotent_and_rollback_restores_prior_batch(tmp_path):
    record = parse_fixture()
    accepted_path = tmp_path / "accepted.json"
    candidate_path = tmp_path / "candidate.json"
    history = tmp_path / "history"
    write_json(accepted_path, accepted([]))
    write_json(candidate_path, batch("candidate-v2", [record]))
    accept_batch(candidate_path, accepted_path, history)
    once = read_json(accepted_path)
    assert once["records"][0]["record_version"] == 1
    write_json(candidate_path, batch("candidate-v3", [deepcopy(record)]))
    accept_batch(candidate_path, accepted_path, history)
    twice = read_json(accepted_path)
    assert twice["records"][0]["record_version"] == 1
    assert twice["records"] == once["records"]
    result = rollback_accepted(accepted_path, history, "accepted-v1")
    assert result["restored_batch_id"] == "accepted-v1"
    assert read_json(accepted_path)["records"] == []


def test_fetch_is_bounded_sequential_cached_and_conditional(tmp_path):
    detail = (FIXTURES / "detail_full.html").read_text(encoding="utf-8")
    sitemap = """<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://fau-preview.catalog.prod.coursedog.com/courses/COP4331</loc></url></urlset>"""
    seen: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, request.headers.get("if-none-match")))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=sitemap, request=request)
        if request.headers.get("if-none-match") == '"fixture-v1"':
            return httpx.Response(304, request=request)
        return httpx.Response(200, text=detail, headers={"ETag": '"fixture-v1"'}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": "test"})
    config = FetchConfig(pace_seconds=0, max_retries=0)
    first = fetch_courses(["COP4331"], cache_dir=tmp_path, batch_id="one", config=config, client=client, sleep=lambda _: None)
    second = fetch_courses(["COP4331"], cache_dir=tmp_path, batch_id="two", config=config, client=client, sleep=lambda _: None)
    client.close()
    assert first["live_request_count"] == 2
    assert second["live_request_count"] == 2
    assert second["results"][0]["cache_status"] == "revalidated_unchanged"
    assert seen == [("/sitemap.xml", None), ("/courses/COP4331", None), ("/sitemap.xml", None), ("/courses/COP4331", '"fixture-v1"')]


def test_fetch_stops_after_persistent_rate_limit(tmp_path):
    sitemap = """<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://example.invalid/courses/COP4331</loc></url>
    <url><loc>https://example.invalid/courses/CDA4102</loc></url></urlset>"""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=sitemap, request=request)
        return httpx.Response(429, headers={"Retry-After": "0"}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = fetch_courses(["COP4331", "CDA4102"], cache_dir=tmp_path, batch_id="limited", config=FetchConfig(max_retries=1, pace_seconds=0), client=client, sleep=lambda _: None)
    client.close()
    assert result["stopped_on_persistent_access_failure"] is True
    assert result["results"] == [{"course_code": "COP4331", "status": "failed", "source_url": "https://catalog.fau.edu/courses/COP4331", "http_status": 429}]
    assert calls == 3
