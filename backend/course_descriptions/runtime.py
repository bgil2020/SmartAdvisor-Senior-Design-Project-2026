"""Bounded session-mode acquisition for exact approved catalog mappings."""
from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import Future
from pathlib import Path
from typing import Any

import httpx

from backend.course_descriptions.models import normalize_course_code, utc_now
from backend.course_descriptions.parser import ParseError, parse_course_detail
from backend.course_descriptions.storage import validate_record
from backend.session_evidence import attach_provenance

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "data" / "course_descriptions" / "sample-manifest.json"
_slot = threading.BoundedSemaphore(1)
_guard = threading.Lock()
_inflight: dict[str, Future] = {}


def _mapping(course_code: str, manifest_path: Path = DEFAULT_MANIFEST) -> str | None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    code = normalize_course_code(course_code)
    url = (manifest.get("detail_urls_discovered_from_published_sitemap") or {}).get(code)
    if code not in set(manifest.get("selected_courses") or []):
        return None
    return str(url) if isinstance(url, str) and url.startswith("https://catalog.fau.edu/courses/") else None


def acquire_exact_course_description(course_code: str, *, client: httpx.Client | None = None) -> dict[str, Any]:
    """Acquire one allowlisted detail page; never discover or construct a URL."""
    code = normalize_course_code(course_code)
    if os.getenv("CATALOG_ACQUISITION_ENABLED", "false").casefold() != "true":
        return {"status": "disabled", "record": None, "request_count": 0, "cleanup": "not_started"}
    url = _mapping(code)
    if not url:
        return {"status": "no_exact_approved_mapping", "record": None, "request_count": 0, "cleanup": "not_started"}
    with _guard:
        future = _inflight.get(code)
        owner = future is None
        if owner:
            future = Future()
            _inflight[code] = future
    timeout = max(0.1, float(os.getenv("CATALOG_ACQUISITION_TIMEOUT_SECONDS", "10")))
    if not owner:
        result = future.result(timeout=timeout + 2)
        return {**result, "coalesced": True, "request_count": 0}
    try:
        result = _run(code, url, timeout=timeout, client=client)
        future.set_result(result)
        return result
    except BaseException as exc:
        safe = {"status": "runtime_error", "record": None, "request_count": 1, "error_type": type(exc).__name__, "cleanup": "attempted"}
        future.set_result(safe)
        return safe
    finally:
        with _guard:
            _inflight.pop(code, None)


def _run(code: str, url: str, *, timeout: float, client: httpx.Client | None) -> dict[str, Any]:
    started = time.monotonic()
    maximum = max(1024, int(os.getenv("CATALOG_ACQUISITION_MAX_BYTES", str(2 * 1024 * 1024))))
    owned = client is None
    session = client or httpx.Client(timeout=timeout, follow_redirects=False, headers={"User-Agent": "SmartAdvisorCourseCollector/1.0 (bounded session acquisition)"})
    try:
        with _slot:
            with session.stream("GET", url) as response:
                if response.status_code in {401, 403}:
                    return {"status": "access_denied", "record": None, "request_count": 1, "cleanup": "completed"}
                if response.status_code != 200:
                    return {"status": "source_unavailable", "record": None, "request_count": 1, "http_status": response.status_code, "cleanup": "completed"}
                content = bytearray()
                for part in response.iter_bytes():
                    content.extend(part)
                    if len(content) > maximum:
                        return {"status": "response_too_large", "record": None, "request_count": 1, "cleanup": "completed"}
                encoding = response.encoding or "utf-8"
                html = bytes(content).decode(encoding, errors="replace")
                final_url = str(response.url)
        record = parse_course_detail(
            html,
            expected_course_code=code,
            source_url=final_url,
            fetched_at=utc_now(),
            raw_evidence_ref="session-memory:catalog-html",
        )
        errors = validate_record(record)
        if errors:
            return {"status": "candidate_rejected", "record": None, "request_count": 1, "cleanup": "completed"}
        return {
            "status": "acquired",
            "record": attach_provenance(record),
            "request_count": 1,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "cleanup": "completed",
        }
    except httpx.TimeoutException:
        return {"status": "timeout", "record": None, "request_count": 1, "cleanup": "completed"}
    except (httpx.TransportError, ParseError):
        return {"status": "candidate_rejected", "record": None, "request_count": 1, "cleanup": "completed"}
    finally:
        if owned:
            session.close()
