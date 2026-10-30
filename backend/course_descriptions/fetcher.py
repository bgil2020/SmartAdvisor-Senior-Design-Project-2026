"""Bounded, sequential HTTP acquisition for FAU course detail pages."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx

from .http import FetchConfig, FetchStopped, bounded_get
from .models import BATCH_ID_RE, normalize_course_code, sha256_text, utc_now, write_json

CATALOG_ORIGIN = "https://catalog.fau.edu"
SITEMAP_URL = f"{CATALOG_ORIGIN}/sitemap.xml"
ALLOWED_HOSTS = {"catalog.fau.edu"}
MAX_COURSES = 5
USER_AGENT = "SmartAdvisorCourseCollector/1.0 (manual academic project; https://github.com/bgil2020/SmartAdvisor-Senior-Design-Project-2026)"
LOG = logging.getLogger(__name__)


def _request(
    client: httpx.Client,
    url: str,
    *,
    headers: dict[str, str] | None,
    config: FetchConfig,
    sleep: Callable[[float], None],
) -> tuple[httpx.Response, int]:
    return bounded_get(client, url, allowed_hosts=ALLOWED_HOSTS, headers=headers, config=config, sleep=sleep)


def discover_detail_urls(sitemap_text: str, course_codes: list[str]) -> dict[str, str]:
    wanted = {normalize_course_code(code) for code in course_codes}
    found: dict[str, str] = {}
    root = ElementTree.fromstring(sitemap_text)
    for node in root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url"):
        location = node.findtext("{http://www.sitemaps.org/schemas/sitemap/0.9}loc", "")
        parsed = urlparse(location)
        parts = parsed.path.rstrip("/").split("/")
        if len(parts) == 3 and parts[1] == "courses":
            code = normalize_course_code(parts[2])
            if code in wanted:
                found[code] = f"{CATALOG_ORIGIN}/courses/{parts[2]}"
    return found


def _portable_ref(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def fetch_courses(
    course_codes: list[str],
    *,
    cache_dir: Path,
    batch_id: str,
    config: FetchConfig | None = None,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    config = config or FetchConfig()
    if not BATCH_ID_RE.fullmatch(batch_id):
        raise ValueError("batch_id must be 3-80 safe identifier characters")
    if config.timeout_seconds <= 0 or config.pace_seconds < 0 or config.max_retries < 0:
        raise ValueError("Timeout must be positive; pacing and retries must be non-negative")
    codes = list(dict.fromkeys(normalize_course_code(code) for code in course_codes))
    if not codes or len(codes) > MAX_COURSES:
        raise ValueError(f"Provide between 1 and {MAX_COURSES} unique course codes")
    batch_dir = cache_dir / batch_id
    batch_dir.mkdir(parents=True, exist_ok=False)
    shared_cache = cache_dir / "_cache"
    shared_cache.mkdir(parents=True, exist_ok=True)
    owned_client = client is None
    client = client or httpx.Client(timeout=config.timeout_seconds, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    request_count = 0
    results: list[dict] = []
    stopped = False
    try:
        sitemap_response, used = _request(client, SITEMAP_URL, headers=None, config=config, sleep=sleep)
        request_count += used
        sitemap_response.raise_for_status()
        urls = discover_detail_urls(sitemap_response.text, codes)
        for index, code in enumerate(codes):
            if code not in urls:
                results.append({"course_code": code, "status": "not_found", "error": "No exact course path in published sitemap."})
                continue
            if index:
                sleep(config.pace_seconds)
            url = urls[code]
            cached_html = shared_cache / f"{code}.html"
            cached_meta = shared_cache / f"{code}.json"
            conditional: dict[str, str] = {}
            if cached_html.exists() and cached_meta.exists():
                prior = json.loads(cached_meta.read_text(encoding="utf-8"))
                if prior.get("etag"):
                    conditional["If-None-Match"] = prior["etag"]
                if prior.get("last_modified"):
                    conditional["If-Modified-Since"] = prior["last_modified"]
            try:
                response, used = _request(client, url, headers=conditional, config=config, sleep=sleep)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                request_count += config.max_retries + 1
                results.append({"course_code": code, "status": "failed", "source_url": url, "error": type(exc).__name__})
                stopped = True
                break
            request_count += used
            if response.status_code in {429, 403} or response.status_code >= 500:
                results.append({"course_code": code, "status": "failed", "source_url": url, "http_status": response.status_code})
                stopped = True
                break
            if response.status_code == 304 and cached_html.exists() and cached_meta.exists():
                response_text = cached_html.read_text(encoding="utf-8")
                final_url = url
                cache_status = "revalidated_unchanged"
                headers = json.loads(cached_meta.read_text(encoding="utf-8"))
            elif response.status_code == 200:
                response_text = response.text
                final_url = str(response.url)
                cache_status = "refreshed"
                headers = {"etag": response.headers.get("ETag"), "last_modified": response.headers.get("Last-Modified")}
                cached_html.write_text(response_text, encoding="utf-8")
                write_json(cached_meta, headers)
            else:
                results.append({"course_code": code, "status": "not_found" if response.status_code == 404 else "failed", "source_url": url, "http_status": response.status_code})
                continue
            fetched_at = utc_now()
            raw_path = batch_dir / f"{code}.html"
            raw_path.write_text(response_text, encoding="utf-8")
            meta = {
                "course_code": code,
                "status": "fetched",
                "cache_status": cache_status,
                "source_url": final_url,
                "fetched_at": fetched_at,
                "raw_evidence_ref": _portable_ref(raw_path),
                "raw_sha256": sha256_text(response_text),
                "etag": headers.get("etag"),
                "last_modified": headers.get("last_modified"),
            }
            write_json(batch_dir / f"{code}.json", meta)
            results.append(meta)
            LOG.info("Fetched course=%s status=%s cache=%s", code, response.status_code, cache_status)
    finally:
        if owned_client:
            client.close()
    manifest = {
        "batch_id": batch_id,
        "requested_courses": codes,
        "request_budget": (1 + len(codes)) * (config.max_retries + 1),
        "live_request_count": request_count,
        "stopped_on_persistent_access_failure": stopped,
        "results": results,
    }
    write_json(batch_dir / "fetch-manifest.json", manifest)
    return manifest
