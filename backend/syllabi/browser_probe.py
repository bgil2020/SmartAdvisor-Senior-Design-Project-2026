"""Browser-event probe guard with conservative access-denial circuit breaking.

This module is browser-driver agnostic so normal tests remain offline. A concrete
driver must label responses as ``essential_document``, ``telemetry``, or
``other`` from its observed page lifecycle; it must not construct private API
requests. The guard owns cancellation and cleanup once a limit is reached.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from .parser import classify_browser_observation


class BrowserProbeSession(Protocol):
    def navigate(self, url: str) -> None: ...
    def events(self) -> Iterable[dict]: ...
    def cancel(self) -> None: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class BrowserProbeLimits:
    essential_request_budget: int = 2
    access_denial_threshold: int = 1
    total_response_budget: int = 20

    def __post_init__(self) -> None:
        if self.essential_request_budget < 1 or self.access_denial_threshold < 1 or self.total_response_budget < 1:
            raise ValueError("Browser probe limits must be positive")


def probe_browser_session(session: BrowserProbeSession, url: str, *, limits: BrowserProbeLimits | None = None) -> dict:
    """Observe one logical navigation and always close its page/context.

    Event dictionaries are intentionally small and sanitized:
    ``response`` events carry ``status`` and ``role``; ``snapshot`` events carry
    rendered ``html`` and ``final_url``. Reaching the first essential 401/403,
    the essential budget, or the total response budget cancels the session.
    """
    limits = limits or BrowserProbeLimits()
    logical_navigations = 0
    responses = essential = telemetry = denials = 0
    failed_requests: list[dict] = []
    status = "incomplete_extraction"
    stop_reason = "event_stream_ended"
    cancelled = False

    def cancel(reason: str) -> None:
        nonlocal cancelled, stop_reason
        if not cancelled:
            session.cancel()
            cancelled = True
        stop_reason = reason

    try:
        session.navigate(url)
        logical_navigations = 1
        for event in session.events():
            kind = event.get("kind")
            if kind == "response":
                responses += 1
                role = event.get("role", "other")
                response_status = int(event.get("status", 0))
                if role == "essential_document":
                    essential += 1
                    if response_status >= 400:
                        failed_requests.append({"status": response_status, "essential": True})
                    if response_status in {401, 403}:
                        denials += 1
                        if denials >= limits.access_denial_threshold:
                            status = "generic_access_denied"
                            cancel("essential_access_denied")
                            break
                    if essential >= limits.essential_request_budget:
                        cancel("essential_request_budget_exhausted")
                        break
                elif role == "telemetry":
                    telemetry += 1
                    if response_status >= 400:
                        failed_requests.append({"status": response_status, "essential": False})
                if responses >= limits.total_response_budget:
                    cancel("total_response_budget_exhausted")
                    break
            elif kind == "snapshot":
                status = classify_browser_observation(
                    str(event.get("html", "")),
                    str(event.get("final_url", url)),
                    failed_requests=failed_requests,
                )
                if status == "anonymous_full_document":
                    stop_reason = "rendered_document_ready"
                    break
            elif kind == "error":
                raise RuntimeError(str(event.get("error", "browser probe failed")))
    except Exception:
        cancel("browser_error")
        raise
    finally:
        session.close()

    return {
        "status": status,
        "stop_reason": stop_reason,
        "logical_navigations": logical_navigations,
        "actual_observed_responses": responses,
        "essential_document_requests": essential,
        "telemetry_responses": telemetry,
        "access_denials": denials,
        "cancelled": cancelled,
        "limits": {
            "essential_request_budget": limits.essential_request_budget,
            "access_denial_threshold": limits.access_denial_threshold,
            "total_response_budget": limits.total_response_budget,
        },
    }
