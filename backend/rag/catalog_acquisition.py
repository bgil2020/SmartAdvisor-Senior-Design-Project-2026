"""Opt-in, bounded catalog acquisition for one eligible course-description gap."""
from __future__ import annotations

import os
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Callable

import httpx

from backend.course_descriptions.fetcher import FetchConfig, fetch_courses
from backend.course_descriptions.http import (
    FetchCancelled,
    FetchDeadlineExceeded,
    FetchRequestBudgetExceeded,
    FetchResponseTooLarge,
    FetchStopped,
)
from backend.course_descriptions.models import normalize_course_code
from backend.course_descriptions.storage import validate_batch
from backend.course_descriptions.workflow import parse_fetch_batch

from .models import AcquisitionPlan
from .operational_storage import OperationalStorageError, RuntimeGenerationStore

ROOT = Path(__file__).resolve().parents[2]


def _bool_environment(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def _float_environment(name: str, default: float, *, minimum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value >= minimum else default


def _int_environment(name: str, default: int, *, minimum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value >= minimum else default


@dataclass(frozen=True)
class CatalogAcquisitionSettings:
    enabled: bool = False
    data_root: Path = ROOT / "data" / "course_descriptions"
    request_timeout_seconds: float = 10.0
    total_deadline_seconds: float = 30.0
    pace_seconds: float = 0.25
    max_retries: int = 1
    max_retry_after_seconds: float = 2.0
    max_requests: int = 6
    max_response_bytes: int = 8 * 1024 * 1024
    max_redirects: int = 1
    max_concurrent: int = 1
    failure_cooldown_seconds: float = 60.0
    coordination_cache_size: int = 128

    @classmethod
    def from_environment(cls) -> "CatalogAcquisitionSettings":
        configured = Path(os.getenv("RAG_CATALOG_ACQUISITION_ROOT", str(cls.data_root)))
        if not configured.is_absolute():
            configured = ROOT / configured
        return cls(
            enabled=_bool_environment("RAG_CATALOG_ACQUISITION_ENABLED"),
            data_root=configured,
            request_timeout_seconds=_float_environment("RAG_CATALOG_REQUEST_TIMEOUT_SECONDS", 10.0, minimum=0.1),
            total_deadline_seconds=_float_environment("RAG_CATALOG_TOTAL_DEADLINE_SECONDS", 30.0, minimum=0.5),
            pace_seconds=_float_environment("RAG_CATALOG_PACE_SECONDS", 0.25, minimum=0.0),
            max_retries=_int_environment("RAG_CATALOG_MAX_RETRIES", 1, minimum=0),
            max_retry_after_seconds=_float_environment("RAG_CATALOG_MAX_RETRY_AFTER_SECONDS", 2.0, minimum=0.0),
            max_requests=_int_environment("RAG_CATALOG_MAX_REQUESTS", 6, minimum=2),
            max_response_bytes=_int_environment("RAG_CATALOG_MAX_RESPONSE_BYTES", 8 * 1024 * 1024, minimum=1024),
            max_redirects=_int_environment("RAG_CATALOG_MAX_REDIRECTS", 1, minimum=0),
            max_concurrent=_int_environment("RAG_CATALOG_MAX_CONCURRENT", 1, minimum=1),
            failure_cooldown_seconds=_float_environment("RAG_CATALOG_FAILURE_COOLDOWN_SECONDS", 60.0, minimum=0.0),
            coordination_cache_size=_int_environment("RAG_CATALOG_COORDINATION_CACHE_SIZE", 128, minimum=1),
        )

    def key(self) -> tuple[Any, ...]:
        return tuple(asdict(self).values())


@dataclass(frozen=True)
class CatalogAcquisitionResult:
    outcome: str
    course_code: str | None
    attempted: bool = False
    coalesced: bool = False
    reason: str | None = None
    source_url: str | None = None
    generation_id: str | None = None
    request_count: int = 0
    redirect_count: int = 0
    retry_count: int = 0
    cooldown_seconds: float | None = None

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _Flight:
    event: threading.Event
    result: CatalogAcquisitionResult | None = None


def _has_course_description(store: RuntimeGenerationStore, course_code: str) -> bool:
    snapshot = store.snapshot()
    if snapshot is None:
        return False
    return any(
        chunk.record_category == "course_description" and chunk.course_code == course_code
        for chunk in snapshot.retriever.chunks
    )


class CatalogAcquisitionCoordinator:
    """Coalesce per-course work and bound same-process external acquisition."""

    def __init__(
        self,
        settings: CatalogAcquisitionSettings,
        *,
        client_factory: Callable[[], httpx.Client] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.settings = settings
        self.client_factory = client_factory
        self.clock = clock
        self._guard = threading.Lock()
        self._flights: dict[str, _Flight] = {}
        self._cooldowns: OrderedDict[str, tuple[float, CatalogAcquisitionResult]] = OrderedDict()
        self._external_slots = threading.BoundedSemaphore(settings.max_concurrent)

    def _cooldown_result(self, course_code: str) -> CatalogAcquisitionResult | None:
        now = self.clock()
        expired = [key for key, (until, _) in self._cooldowns.items() if until <= now]
        for key in expired:
            self._cooldowns.pop(key, None)
        item = self._cooldowns.get(course_code)
        if item is None:
            return None
        until, prior = item
        self._cooldowns.move_to_end(course_code)
        return CatalogAcquisitionResult(
            outcome="cooldown_active",
            course_code=course_code,
            reason=f"A recent bounded acquisition ended as {prior.outcome}; retry is temporarily cooled down.",
            cooldown_seconds=max(0.0, round(until - now, 3)),
        )

    def _remember_failure(self, course_code: str, result: CatalogAcquisitionResult) -> None:
        if result.outcome in {"published", "unchanged", "local_evidence_available", "cancelled"}:
            return
        with self._guard:
            self._cooldowns[course_code] = (self.clock() + self.settings.failure_cooldown_seconds, result)
            self._cooldowns.move_to_end(course_code)
            while len(self._cooldowns) > self.settings.coordination_cache_size:
                self._cooldowns.popitem(last=False)

    def execute(
        self,
        plan: AcquisitionPlan,
        *,
        runtime_store: RuntimeGenerationStore,
        supported_courses: set[str],
        cancelled: threading.Event | None = None,
    ) -> CatalogAcquisitionResult:
        cancel_event = cancelled or threading.Event()
        course_code = normalize_course_code(plan.course_code or "")
        if not self.settings.enabled:
            return CatalogAcquisitionResult("disabled", course_code or None, reason="Catalog acquisition is opt-in and disabled.")
        if (not plan.eligible or plan.clarification_required or plan.evidence_gap != "appropriate_source_absent" or
                plan.source_categories != ["course_description"] or not course_code):
            return CatalogAcquisitionResult("ineligible_plan", course_code or None, reason="The readiness plan is not one bounded catalog-description miss.")
        if course_code not in supported_courses:
            return CatalogAcquisitionResult("unsupported_course", course_code, reason="The course is not present in the approved project schedule dataset.")
        snapshot = runtime_store.snapshot()
        if snapshot is None:
            return CatalogAcquisitionResult("storage_uninitialized", course_code, reason="Initialize operational storage explicitly before acquisition.")
        if snapshot.recovered_from_last_good:
            return CatalogAcquisitionResult("storage_recovery_required", course_code, reason="Repair or explicitly recover the current generation before acquisition.")
        if _has_course_description(runtime_store, course_code):
            return CatalogAcquisitionResult("local_evidence_available", course_code, reason="Another request already published this course description.")

        with self._guard:
            cooldown = self._cooldown_result(course_code)
            if cooldown is not None:
                return cooldown
            flight = self._flights.get(course_code)
            if flight is None:
                flight = _Flight(threading.Event())
                self._flights[course_code] = flight
                leader = True
            else:
                leader = False

        if not leader:
            while not flight.event.wait(0.05):
                if cancel_event.is_set():
                    return CatalogAcquisitionResult("cancelled", course_code, reason="Request cancelled while waiting for matching acquisition.")
            assert flight.result is not None
            return replace(flight.result, coalesced=True, attempted=False)

        result: CatalogAcquisitionResult
        try:
            deadline = self.clock() + self.settings.total_deadline_seconds
            while not self._external_slots.acquire(timeout=0.05):
                if cancel_event.is_set():
                    result = CatalogAcquisitionResult("cancelled", course_code, reason="Request cancelled before external acquisition.")
                    return result
                if self.clock() >= deadline:
                    result = CatalogAcquisitionResult("temporarily_unavailable", course_code, reason="Timed out waiting for the bounded external acquisition slot.")
                    return result
            try:
                if _has_course_description(runtime_store, course_code):
                    result = CatalogAcquisitionResult("local_evidence_available", course_code, reason="Evidence became available before collection started.")
                else:
                    result = self._execute_once(course_code, runtime_store=runtime_store, cancelled=cancel_event)
            finally:
                self._external_slots.release()
            self._remember_failure(course_code, result)
            return result
        finally:
            with self._guard:
                active = self._flights.pop(course_code, None)
                if active is not None:
                    # A return from the try block is materialized before finally.
                    active.result = locals().get("result") or CatalogAcquisitionResult(
                        "cancelled", course_code, reason="Acquisition ended before producing a result."
                    )
                    active.event.set()

    def _execute_once(
        self,
        course_code: str,
        *,
        runtime_store: RuntimeGenerationStore,
        cancelled: threading.Event,
    ) -> CatalogAcquisitionResult:
        settings = self.settings
        acquisition_deadline = self.clock() + settings.total_deadline_seconds
        batch_id = f"api-{course_code.lower()}-{uuid.uuid4().hex[:12]}"
        raw_root = settings.data_root / "raw"
        candidate_path = settings.data_root / "candidates" / f"{batch_id}.json"
        config = FetchConfig(
            timeout_seconds=settings.request_timeout_seconds,
            pace_seconds=settings.pace_seconds,
            max_retries=settings.max_retries,
            max_retry_after_seconds=settings.max_retry_after_seconds,
            total_deadline_seconds=settings.total_deadline_seconds,
            max_response_bytes=settings.max_response_bytes,
            max_redirects=settings.max_redirects,
            max_requests=settings.max_requests,
        )
        client = self.client_factory() if self.client_factory else httpx.Client(
            timeout=settings.request_timeout_seconds,
            follow_redirects=False,
            headers={"User-Agent": "SmartAdvisorCourseCollector/1.0 (bounded API acquisition)"},
        )
        try:
            manifest = fetch_courses(
                [course_code], cache_dir=raw_root, batch_id=batch_id,
                config=config, client=client, cancelled=cancelled.is_set,
            )
        except FetchCancelled as exc:
            return CatalogAcquisitionResult("cancelled", course_code, attempted=True, reason=str(exc))
        except FetchDeadlineExceeded as exc:
            return CatalogAcquisitionResult("timeout", course_code, attempted=True, reason=str(exc))
        except FetchResponseTooLarge as exc:
            return CatalogAcquisitionResult("response_too_large", course_code, attempted=True, reason=str(exc))
        except FetchRequestBudgetExceeded as exc:
            return CatalogAcquisitionResult("request_budget_exceeded", course_code, attempted=True, reason=str(exc))
        except FetchStopped as exc:
            return CatalogAcquisitionResult("source_rejected", course_code, attempted=True, reason=str(exc))
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            outcome = "access_denied" if status in {401, 403} else "discovery_failure"
            return CatalogAcquisitionResult(outcome, course_code, attempted=True, reason=f"Catalog discovery returned HTTP {status}.")
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            return CatalogAcquisitionResult("temporarily_unavailable", course_code, attempted=True, reason=f"Catalog request failed ({type(exc).__name__}).")
        except Exception as exc:
            return CatalogAcquisitionResult("discovery_failure", course_code, attempted=True, reason=f"Catalog discovery could not be processed ({type(exc).__name__}).")
        finally:
            client.close()

        metrics = {
            "request_count": int(manifest.get("live_request_count", 0)),
            "redirect_count": int(manifest.get("redirect_count", 0)),
            "retry_count": int(manifest.get("retry_count", 0)),
        }
        if self.clock() >= acquisition_deadline:
            return CatalogAcquisitionResult("timeout", course_code, attempted=True, reason="Catalog acquisition deadline expired before candidate processing.", **metrics)
        results = manifest.get("results", [])
        source = next((item for item in results if item.get("course_code") == course_code), None)
        if source is None:
            return CatalogAcquisitionResult("source_not_found", course_code, attempted=True, reason="Catalog discovery returned no result for the course.", **metrics)
        if source.get("status") != "fetched":
            status = source.get("http_status")
            if status in {401, 403}:
                outcome = "access_denied"
            elif source.get("status") == "not_found":
                outcome = "source_not_found"
            else:
                outcome = "temporarily_unavailable"
            return CatalogAcquisitionResult(outcome, course_code, attempted=True, reason="Catalog source did not return one usable detail page.", source_url=source.get("source_url"), **metrics)
        if cancelled.is_set():
            return CatalogAcquisitionResult("cancelled", course_code, attempted=True, reason="Request cancelled before candidate parsing.", **metrics)

        try:
            candidate = parse_fetch_batch(raw_root / batch_id, candidate_path)
            validation = validate_batch(candidate)
        except Exception as exc:
            return CatalogAcquisitionResult("candidate_rejected", course_code, attempted=True, reason=f"Candidate parsing failed ({type(exc).__name__}).", source_url=source.get("source_url"), **metrics)
        records = candidate.get("records", [])
        if (not validation["valid"] or len(records) != 1 or records[0].get("course_code") != course_code or
                records[0].get("record_category") != "course_description"):
            return CatalogAcquisitionResult("candidate_rejected", course_code, attempted=True, reason="Validated candidate identity/category did not match the requested course.", source_url=source.get("source_url"), **metrics)
        if cancelled.is_set():
            return CatalogAcquisitionResult("cancelled", course_code, attempted=True, reason="Request cancelled before operational publication.", source_url=source.get("source_url"), **metrics)
        if self.clock() >= acquisition_deadline:
            return CatalogAcquisitionResult("timeout", course_code, attempted=True, reason="Catalog acquisition deadline expired before operational publication.", source_url=source.get("source_url"), **metrics)
        try:
            publication = runtime_store.publish(course_batches=[candidate_path], syllabus_batches=[])
        except (OperationalStorageError, OSError, ValueError) as exc:
            return CatalogAcquisitionResult("publication_failed", course_code, attempted=True, reason=f"Operational publication failed ({type(exc).__name__}).", source_url=source.get("source_url"), **metrics)
        return CatalogAcquisitionResult(
            "published" if publication.changed else "unchanged",
            course_code,
            attempted=True,
            reason="Validated catalog candidate was published and activated in the running process.",
            source_url=records[0]["source"]["url"],
            generation_id=publication.generation_id,
            **metrics,
        )


_coordinator_guard = threading.Lock()
_coordinators: dict[tuple[Any, ...], CatalogAcquisitionCoordinator] = {}


def get_catalog_acquisition_coordinator(settings: CatalogAcquisitionSettings) -> CatalogAcquisitionCoordinator:
    key = settings.key()
    with _coordinator_guard:
        coordinator = _coordinators.get(key)
        if coordinator is None:
            coordinator = CatalogAcquisitionCoordinator(settings)
            _coordinators[key] = coordinator
        return coordinator


def clear_catalog_acquisition_coordinators() -> None:
    with _coordinator_guard:
        _coordinators.clear()
