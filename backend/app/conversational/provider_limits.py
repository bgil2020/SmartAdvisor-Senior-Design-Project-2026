"""Shared bounds for optional Gemini provider calls."""
from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MAX_OUTPUT_TOKENS = 512
_budget_lock = threading.Lock()
_budget_settings: dict[str, str] = {}
_budget_used: dict[str, int] = {}


class ProviderRequestBudgetExhausted(RuntimeError):
    """Raised before transport when a bounded live-test budget is exhausted."""


def gemini_max_output_tokens() -> int:
    raw = os.getenv("GEMINI_MAX_OUTPUT_TOKENS", str(DEFAULT_GEMINI_MAX_OUTPUT_TOKENS)).strip()
    value = int(raw)
    if not 64 <= value <= 2048:
        raise ValueError("GEMINI_MAX_OUTPUT_TOKENS must be between 64 and 2048")
    return value


def openrouter_max_output_tokens() -> int:
    raw = os.getenv("OPENROUTER_MAX_OUTPUT_TOKENS", str(DEFAULT_GEMINI_MAX_OUTPUT_TOKENS)).strip()
    value = int(raw)
    if not 64 <= value <= 2048:
        raise ValueError("OPENROUTER_MAX_OUTPUT_TOKENS must be between 64 and 2048")
    return value


def claim_provider_request(
    budget_variable: str = "GEMINI_TEST_REQUEST_BUDGET",
    provider_name: str = "Gemini",
) -> int | None:
    """Claim one provider request when a bounded live-test budget is configured.

    Normal application operation is unchanged when the variable is absent.
    The bounded live verifier sets the limit to one, so any unexpected parser,
    retry, or second generation call fails before provider transport begins.
    """
    raw = os.getenv(budget_variable, "").strip()
    if not raw:
        return None
    limit = int(raw)
    if not 1 <= limit <= 3:
        raise ValueError(f"{budget_variable} must be between 1 and 3")

    with _budget_lock:
        if _budget_settings.get(budget_variable) != raw:
            _budget_settings[budget_variable] = raw
            _budget_used[budget_variable] = 0
        used = _budget_used.get(budget_variable, 0)
        if used >= limit:
            raise ProviderRequestBudgetExhausted(f"{provider_name} provider request budget exhausted")
        used += 1
        _budget_used[budget_variable] = used
        logger.info("%s provider request budget claim %d/%d", provider_name, used, limit)
        return used
