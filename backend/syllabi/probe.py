"""Bounded anonymous probes of user-visible Simple Syllabus document URLs."""
from __future__ import annotations

import time
from typing import Callable

import httpx

from backend.course_descriptions.http import FetchConfig, bounded_get
from .parser import classify_page

ALLOWED_HOSTS = {"fau.simplesyllabus.com"}
MAX_DOCUMENTS = 3
USER_AGENT = "SmartAdvisorSyllabusCollector/1.0 (manual academic project)"


def probe_documents(documents: list[dict], *, config: FetchConfig | None = None, client: httpx.Client | None = None, sleep: Callable[[float], None] = time.sleep) -> dict:
    if not 1 <= len(documents) <= MAX_DOCUMENTS:
        raise ValueError("Provide between 1 and 3 documents")
    config = config or FetchConfig(max_retries=1)
    owned = client is None
    client = client or httpx.Client(timeout=config.timeout_seconds, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    results, request_count = [], 0
    stopped = False
    try:
        for index, document in enumerate(documents):
            if index:
                sleep(config.pace_seconds)
            response, used = bounded_get(client, document["view_url"], allowed_hosts=ALLOWED_HOSTS, headers=None, config=config, sleep=sleep)
            request_count += used
            classification = classify_page(response.text, str(response.url), response.status_code)
            if response.status_code in {403, 429}:
                stopped = True
            results.append({**document, "status": "restricted" if classification == "restricted" else classification, "http_status": response.status_code, "final_url": str(response.url), "rendering_required": classification == "library_shell"})
            if stopped:
                break
    finally:
        if owned:
            client.close()
    return {"requested": len(documents), "live_request_count": request_count, "request_budget": len(documents) * (config.max_retries + 1), "stopped_on_access_block": stopped, "results": results}
