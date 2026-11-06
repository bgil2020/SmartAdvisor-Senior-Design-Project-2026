"""Shared bounded HTTP primitive for approved SmartAdvisor source adapters."""
from __future__ import annotations

import email.utils
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urljoin, urlparse

import httpx


class FetchStopped(RuntimeError):
    """The request would leave the allowlist or continue after an access block."""


class FetchCancelled(FetchStopped):
    """The calling request was cancelled before acquisition could publish."""


class FetchDeadlineExceeded(FetchStopped):
    """The bounded whole-acquisition deadline expired."""


class FetchResponseTooLarge(FetchStopped):
    """A source response exceeded the configured byte budget."""


class FetchRequestBudgetExceeded(FetchStopped):
    """The acquisition would exceed its total request budget."""


@dataclass
class FetchConfig:
    timeout_seconds: float = 20.0
    pace_seconds: float = 1.0
    max_retries: int = 2
    max_retry_after_seconds: float = 30.0
    total_deadline_seconds: float = 45.0
    max_response_bytes: int = 8 * 1024 * 1024
    max_redirects: int = 2
    max_requests: int | None = None


@dataclass
class FetchStats:
    requests: int = 0
    redirects: int = 0
    retries: int = 0


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
    deadline: float | None = None,
    cancelled: Callable[[], bool] | None = None,
    remaining_requests: int | None = None,
    max_response_bytes: int | None = None,
) -> tuple[httpx.Response, FetchStats]:
    cancelled = cancelled or (lambda: False)
    deadline = deadline if deadline is not None else time.monotonic() + config.total_deadline_seconds
    byte_limit = max_response_bytes if max_response_bytes is not None else config.max_response_bytes

    def check_active() -> None:
        if cancelled():
            raise FetchCancelled("Catalog acquisition was cancelled")
        if time.monotonic() >= deadline:
            raise FetchDeadlineExceeded("Catalog acquisition exceeded its total deadline")

    def check_url(value: str) -> None:
        parsed = urlparse(value)
        if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
            raise FetchStopped("Refusing request or redirect outside the explicit HTTPS source allowlist")

    def wait(delay: float) -> None:
        end = time.monotonic() + delay
        while time.monotonic() < end:
            check_active()
            sleep(min(0.1, max(0.0, end - time.monotonic())))

    check_url(url)
    stats = FetchStats()
    for attempt in range(config.max_retries + 1):
        current_url = url
        redirect_count = 0
        response: httpx.Response | None = None
        try:
            while True:
                check_active()
                if remaining_requests is not None and stats.requests >= remaining_requests:
                    raise FetchRequestBudgetExceeded("Catalog acquisition exhausted its request budget")
                stats.requests += 1
                with client.stream("GET", current_url, headers=headers or {}, follow_redirects=False) as streamed:
                    content = bytearray()
                    for block in streamed.iter_bytes():
                        check_active()
                        content.extend(block)
                        if len(content) > byte_limit:
                            raise FetchResponseTooLarge(f"Catalog response exceeded {byte_limit} bytes")
                    response = httpx.Response(
                        streamed.status_code,
                        headers=streamed.headers,
                        content=bytes(content),
                        request=streamed.request,
                        extensions=streamed.extensions,
                    )
                if response.is_redirect:
                    location = response.headers.get("Location")
                    if not location:
                        return response, stats
                    redirect_count += 1
                    stats.redirects += 1
                    if redirect_count > config.max_redirects:
                        raise FetchStopped("Catalog redirect limit exceeded")
                    current_url = urljoin(current_url, location)
                    check_url(current_url)
                    continue
                break
            if response.status_code not in {429, 500, 502, 503, 504}:
                return response, stats
        except (httpx.TimeoutException, httpx.TransportError):
            if attempt == config.max_retries:
                raise
        if attempt == config.max_retries:
            assert response is not None
            return response, stats
        stats.retries += 1
        wait(retry_delay(response, attempt, config.max_retry_after_seconds))
    raise AssertionError("unreachable")
