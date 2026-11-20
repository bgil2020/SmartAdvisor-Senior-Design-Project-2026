"""Optional process-local acquisition caps for explicitly bounded live tests.

Normal runtime behavior is unchanged unless an ACQUISITION_TEST_*_BUDGET
environment variable is present. A token is claimed before any network or
browser work begins, so an exhausted budget fails closed without an external
request.
"""
from __future__ import annotations

import os
import threading

_ENV = {
    "catalog": "ACQUISITION_TEST_CATALOG_BUDGET",
    "syllabus": "ACQUISITION_TEST_SYLLABUS_BUDGET",
}
_lock = threading.Lock()
_used = {"catalog": 0, "syllabus": 0}


def claim_test_budget(source: str) -> dict[str, int | bool | None]:
    variable = _ENV[source]
    configured = os.getenv(variable)
    if configured is None:
        return {"enforced": False, "allowed": True, "limit": None, "used": None}
    limit = int(configured)
    if limit < 0:
        raise ValueError(f"{variable} must be non-negative")
    with _lock:
        if _used[source] >= limit:
            return {"enforced": True, "allowed": False, "limit": limit, "used": _used[source]}
        _used[source] += 1
        return {"enforced": True, "allowed": True, "limit": limit, "used": _used[source]}


def reset_test_budgets() -> None:
    """Reset process-local counters for isolated tests only."""
    with _lock:
        for source in _used:
            _used[source] = 0
