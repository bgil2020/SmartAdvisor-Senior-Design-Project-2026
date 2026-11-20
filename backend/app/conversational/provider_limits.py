"""Shared bounds for optional Gemini provider calls."""
from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MAX_OUTPUT_TOKENS = 512
_budget_lock = threading.Lock()
_budget_setting: str | None = None
_budget_used = 0


class ProviderRequestBudgetExhausted(RuntimeError):
    """Raised before transport when a bounded live-test budget is exhausted."""


def gemini_max_output_tokens() -> int:
    raw = os.getenv("GEMINI_MAX_OUTPUT_TOKENS", str(DEFAULT_GEMINI_MAX_OUTPUT_TOKENS)).strip()
    value = int(raw)
    if not 64 <= value <= 2048:
        raise ValueError("GEMINI_MAX_OUTPUT_TOKENS must be between 64 and 2048")
    return value


def claim_provider_request() -> int | None:
    """Claim one provider request when a bounded live-test budget is configured.

    Normal application operation is unchanged when the variable is absent.
    The bounded live verifier sets the limit to one, so any unexpected parser,
    retry, or second generation call fails before provider transport begins.
    """
    raw = os.getenv("GEMINI_TEST_REQUEST_BUDGET", "").strip()
    if not raw:
        return None
    limit = int(raw)
    if not 1 <= limit <= 3:
        raise ValueError("GEMINI_TEST_REQUEST_BUDGET must be between 1 and 3")

    global _budget_setting, _budget_used
    with _budget_lock:
        if _budget_setting != raw:
            _budget_setting = raw
            _budget_used = 0
        if _budget_used >= limit:
            raise ProviderRequestBudgetExhausted("Gemini provider request budget exhausted")
        _budget_used += 1
        logger.info("Gemini provider request budget claim %d/%d", _budget_used, limit)
        return _budget_used
