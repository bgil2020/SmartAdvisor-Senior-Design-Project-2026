"""Shared bounded HTTP primitive for approved SmartAdvisor source adapters."""
from __future__ import annotations

import email.utils
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urlparse

import httpx


class FetchStopped(RuntimeError):
    """The request would leave the allowlist or continue after an access block."""


@dataclass
class FetchConfig:
    timeout_seconds: float = 20.0
    pace_seconds: float = 1.0
    max_retries: int = 2
    max_retry_after_seconds: float = 30.0


def retry_delay(response: httpx.Response | None, attempt: int, maximum: float) -> float:
    if response is not None and response.headers.get("Retry-After"):
        value = response.headers["Retry-After"]
        try:
            return min(maximum, max(0.0, float(value)))
        except ValueError:
            try:
                when = email.utils.parsedate_to_datetime(value)
                return min(maximum, max(0.0, (when - datetime.now(timezone.utc)).total_seconds()))
            except (TypeError, ValueError):
                pass
    return min(maximum, float(2**attempt))


def bounded_get(
    client: httpx.Client,
    url: str,
    *,
    allowed_hosts: set[str],
    headers: dict[str, str] | None,
    config: FetchConfig,
    sleep: Callable[[float], None],
) -> tuple[httpx.Response, int]:
    if urlparse(url).hostname not in allowed_hosts:
        raise FetchStopped("Refusing request outside the explicit source allowlist")
    requests = 0
    for attempt in range(config.max_retries + 1):
        response: httpx.Response | None = None
        try:
            requests += 1
            response = client.get(url, headers=headers or {})
            if response.url.host not in allowed_hosts:
                raise FetchStopped("Refusing redirect outside the explicit source allowlist")
            if response.status_code not in {429, 500, 502, 503, 504}:
                return response, requests
        except (httpx.TimeoutException, httpx.TransportError):
            if attempt == config.max_retries:
                raise
        if attempt == config.max_retries:
            assert response is not None
            return response, requests
        sleep(retry_delay(response, attempt, config.max_retry_after_seconds))
    raise AssertionError("unreachable")
