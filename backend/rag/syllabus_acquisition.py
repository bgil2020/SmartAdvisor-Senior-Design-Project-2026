"""Opt-in syllabus acquisition for exact tracked source mappings only."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from backend.course_descriptions.models import normalize_course_code
from backend.syllabi.models import stable_syllabus_id
from backend.syllabi.storage import validate_batch
from backend.syllabi.workflow import parse_offline_batch

from .catalog_acquisition import (
    CatalogAcquisitionCoordinator,
    CatalogAcquisitionResult,
    CatalogAcquisitionSettings,
    _bool_environment,
    _float_environment,
    _int_environment,
)
from .models import AcquisitionPlan
from .operational_storage import OperationalStorageError, RuntimeGenerationStore

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data" / "syllabi" / "sample-manifest.json"
COLLECTOR = ROOT / "scripts" / "syllabus_browser_collect.py"
DEFAULT_CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


@dataclass(frozen=True)
class SyllabusAcquisitionSettings:
    enabled: bool = False
    data_root: Path = ROOT / "data" / "syllabi"
    chrome_path: Path = DEFAULT_CHROME
    total_deadline_seconds: float = 30.0
    browser_deadline_seconds: float = 20.0
    failure_cooldown_seconds: float = 300.0
    coordination_cache_size: int = 128

    @classmethod
    def from_environment(cls) -> "SyllabusAcquisitionSettings":
        data_root = Path(os.getenv("RAG_SYLLABUS_ACQUISITION_ROOT", str(cls.data_root)))
        chrome = Path(os.getenv("RAG_SYLLABUS_CHROME_PATH", str(cls.chrome_path)))
        if not data_root.is_absolute():
            data_root = ROOT / data_root
        return cls(
            enabled=_bool_environment("RAG_SYLLABUS_ACQUISITION_ENABLED"),
            data_root=data_root,
            chrome_path=chrome,
            total_deadline_seconds=_float_environment("RAG_SYLLABUS_TOTAL_DEADLINE_SECONDS", 30.0, minimum=1.0),
            browser_deadline_seconds=_float_environment("RAG_SYLLABUS_BROWSER_DEADLINE_SECONDS", 20.0, minimum=1.0),
            failure_cooldown_seconds=_float_environment("RAG_SYLLABUS_FAILURE_COOLDOWN_SECONDS", 300.0, minimum=0.0),
            coordination_cache_size=_int_environment("RAG_SYLLABUS_COORDINATION_CACHE_SIZE", 128, minimum=1),
        )

    def key(self) -> tuple[Any, ...]:
        return tuple(asdict(self).values())


def resolve_exact_mapping(course_code: str, term_id: str, section: str) -> dict[str, Any] | None:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    matches = [
        item for item in value.get("documents", [])
        if normalize_course_code(item.get("course_code", "")) == normalize_course_code(course_code)
        and str(item.get("term_id", "")) == str(term_id)
        and str(item.get("section", "")) == str(section)
    ]
    if len(matches) > 1:
        raise ValueError("Tracked syllabus manifest contains duplicate exact mappings")
    return matches[0] if matches else None


def _has_syllabus(store: RuntimeGenerationStore, mapping: dict[str, Any]) -> bool:
    snapshot = store.snapshot()
    if snapshot is None:
        return False
    expected_document = stable_syllabus_id(
        mapping["course_code"], mapping["term_id"], mapping["section"], mapping["source_document_id"]
    )
    return any(
        chunk.record_category == "syllabus"
        and chunk.document_id == expected_document
        and chunk.course_code == normalize_course_code(mapping["course_code"])
        and chunk.term_id == str(mapping["term_id"])
        and chunk.section == str(mapping["section"])
        for chunk in snapshot.retriever.chunks
    )


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def run_browser_subprocess(
    mapping: dict[str, Any],
    *,
    batch_id: str,
    settings: SyllabusAcquisitionSettings,
    cancelled: threading.Event,
) -> dict[str, Any]:
    """Run the existing headless collector with killable process isolation."""
    command = [
        sys.executable,
        str(COLLECTOR),
        "--document-id", mapping["source_document_id"],
        "--batch-id", batch_id,
        "--chrome", str(settings.chrome_path),
        "--raw-root", str(settings.data_root / "raw"),
        "--diagnostics-root", str(settings.data_root / "diagnostics"),
        "--deadline-seconds", str(settings.browser_deadline_seconds),
    ]
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=creationflags,
        start_new_session=os.name != "nt",
    )
    deadline = time.monotonic() + settings.total_deadline_seconds
    while process.poll() is None:
        if cancelled.is_set():
            _terminate_process_tree(process)
            return {"outcome": "cancelled", "reason": "Request cancelled; browser process tree was stopped."}
        if time.monotonic() >= deadline:
            _terminate_process_tree(process)
            return {"outcome": "timeout", "reason": "Syllabus browser deadline expired; browser process tree was stopped."}
        time.sleep(0.05)
    stdout, stderr = process.communicate()
    if process.returncode not in {0, 2}:
        lowered = stderr.casefold()
        outcome = "browser_unavailable" if any(token in lowered for token in ("playwright", "chrome executable", "executable doesn't exist")) else "browser_error"
        return {"outcome": outcome, "reason": f"Headless browser collector exited with code {process.returncode}."}
    try:
        output = json.loads(stdout)
    except json.JSONDecodeError:
        return {"outcome": "browser_error", "reason": "Headless browser collector returned malformed diagnostics."}
    output["outcome"] = "collected" if process.returncode == 0 else "not_collected"
    return output


class SyllabusAcquisitionCoordinator:
    """Exact-mapping syllabus executor using shared process coordination."""

    def __init__(
        self,
        settings: SyllabusAcquisitionSettings,
        *,
        browser_runner: Callable[..., dict[str, Any]] = run_browser_subprocess,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.settings = settings
        self.browser_runner = browser_runner
        coordination_settings = CatalogAcquisitionSettings(
            enabled=True,
            total_deadline_seconds=settings.total_deadline_seconds,
            max_concurrent=1,
            failure_cooldown_seconds=settings.failure_cooldown_seconds,
            coordination_cache_size=settings.coordination_cache_size,
        )
        self.coordination = CatalogAcquisitionCoordinator(coordination_settings, clock=clock)

    def execute(
        self,
        plan: AcquisitionPlan,
        *,
        runtime_store: RuntimeGenerationStore,
        cancelled: threading.Event | None = None,
    ) -> CatalogAcquisitionResult:
        course = normalize_course_code(plan.course_code or "")
        term = str(plan.term_id or "")
        section = str(plan.section or "")
        scope = {"term_id": term or None, "section": section or None}
        if not self.settings.enabled:
            return CatalogAcquisitionResult("disabled", course or None, reason="Syllabus acquisition is opt-in and disabled.", **scope)
        if not course or not term or not section:
            return CatalogAcquisitionResult("missing_required_scope", course or None, reason="Course, term, and section must be explicitly resolved.", **scope)
        if (not plan.eligible or plan.clarification_required or plan.evidence_gap != "appropriate_source_absent" or
                plan.source_categories != ["syllabus"]):
            return CatalogAcquisitionResult("ineligible_plan", course, reason="The readiness plan is not one exact missing syllabus.", **scope)
        mapping = resolve_exact_mapping(course, term, section)
        if mapping is None:
            return CatalogAcquisitionResult("source_unresolved", course, reason="No exact verified syllabus mapping exists for this course, term, and section.", **scope)
        document_id = mapping["source_document_id"]
        scoped = {**scope, "document_id": document_id, "source_url": mapping["view_url"]}
        if mapping.get("observed_access") != "anonymous_full_document":
            return CatalogAcquisitionResult("manual_collection_required", course, reason="The exact mapping has no verified anonymous full-document access result.", **scoped)
        snapshot = runtime_store.snapshot()
        if snapshot is None:
            return CatalogAcquisitionResult("storage_uninitialized", course, reason="Initialize operational storage explicitly before acquisition.", **scoped)
        if snapshot.recovered_from_last_good:
            return CatalogAcquisitionResult("storage_recovery_required", course, reason="Repair or explicitly recover storage before acquisition.", **scoped)
        if _has_syllabus(runtime_store, mapping):
            return CatalogAcquisitionResult("local_evidence_available", course, reason="The exact syllabus is already active locally.", **scoped)

        key = f"syllabus:{course}:{term}:{section}:{document_id}"
        return self.coordination.execute_coordinated(
            key=key,
            course_code=course,
            local_check=lambda: _has_syllabus(runtime_store, mapping),
            local_result=lambda: CatalogAcquisitionResult("local_evidence_available", course, reason="The exact syllabus became available before collection started.", **scoped),
            work=lambda event: self._execute_once(mapping, runtime_store=runtime_store, cancelled=event),
            cancelled=cancelled,
        )

    def _execute_once(
        self,
        mapping: dict[str, Any],
        *,
        runtime_store: RuntimeGenerationStore,
        cancelled: threading.Event,
    ) -> CatalogAcquisitionResult:
        course = normalize_course_code(mapping["course_code"])
        term, section, document_id = str(mapping["term_id"]), str(mapping["section"]), mapping["source_document_id"]
        scoped = {"term_id": term, "section": section, "document_id": document_id, "source_url": mapping["view_url"]}
        batch_id = f"api-{course.lower()}-{term}-{section}-{uuid.uuid4().hex[:10]}"
        browser = self.browser_runner(
            mapping,
            batch_id=batch_id,
            settings=self.settings,
            cancelled=cancelled,
        )
        diagnostic_id = browser.get("diagnostic_id") or batch_id
        if browser.get("outcome") != "collected":
            if browser.get("outcome") in {"cancelled", "timeout", "browser_unavailable", "browser_error"}:
                return CatalogAcquisitionResult(browser["outcome"], course, attempted=True, reason=browser.get("reason"), diagnostic_id=diagnostic_id, **scoped)
            probe = browser.get("probe", {})
            status = probe.get("status")
            outcome = {
                "generic_access_denied": "access_denied",
                "explicit_login_required": "manual_collection_required",
                "explicit_automation_restriction": "manual_collection_required",
            }.get(status, "incomplete_extraction")
            return CatalogAcquisitionResult(
                outcome, course, attempted=True,
                reason="The bounded anonymous browser did not produce a complete syllabus document.",
                stop_reason=probe.get("stop_reason"),
                browser_response_count=int(probe.get("actual_observed_responses", 0)),
                essential_request_count=int(probe.get("essential_document_requests", 0)),
                diagnostic_id=diagnostic_id,
                **scoped,
            )
        probe = browser.get("probe", {})
        raw_path = self.settings.data_root / "raw" / batch_id / f"{document_id}.html"
        if not raw_path.is_file() or probe.get("status") != "anonymous_full_document":
            return CatalogAcquisitionResult("incomplete_extraction", course, attempted=True, reason="Browser success did not leave one complete expected raw document.", **scoped)
        if cancelled.is_set():
            return CatalogAcquisitionResult("cancelled", course, attempted=True, reason="Request cancelled before syllabus parsing.", **scoped)
        candidate_path = self.settings.data_root / "candidates" / f"{batch_id}.json"
        candidate_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            candidate = parse_offline_batch(MANIFEST, self.settings.data_root / "raw" / batch_id, candidate_path, batch_id)
            validation = validate_batch(candidate)
        except Exception as exc:
            return CatalogAcquisitionResult("invalid_candidate", course, attempted=True, reason=f"Syllabus parsing failed ({type(exc).__name__}).", **scoped)
        records = candidate.get("records", [])
        expected_id = stable_syllabus_id(course, term, section, document_id)
        if len(records) != 1:
            error_code = next((item.get("error_code") for item in candidate.get("outcomes", []) if item.get("source_document_id") == document_id), None)
            outcome = "identity_mismatch" if error_code in {"course_identity_mismatch", "term_identity_mismatch", "section_identity_mismatch"} else "invalid_candidate"
            return CatalogAcquisitionResult(outcome, course, attempted=True, reason=f"Syllabus candidate was rejected ({error_code or 'no complete record'}).", **scoped)
        record = records[0]
        if (not validation["valid"] or record.get("record_id") != expected_id or
                record.get("source", {}).get("source_id") != document_id or
                record.get("source", {}).get("url") != mapping["view_url"]):
            return CatalogAcquisitionResult("identity_mismatch", course, attempted=True, reason="Candidate identity/provenance did not match the exact manifest mapping.", **scoped)
        if cancelled.is_set():
            return CatalogAcquisitionResult("cancelled", course, attempted=True, reason="Request cancelled before operational publication.", **scoped)
        try:
            publication = runtime_store.publish(course_batches=[], syllabus_batches=[candidate_path])
        except (OperationalStorageError, OSError, ValueError) as exc:
            return CatalogAcquisitionResult("publication_failed", course, attempted=True, reason=f"Operational publication failed ({type(exc).__name__}).", **scoped)
        return CatalogAcquisitionResult(
            "published" if publication.changed else "unchanged",
            course,
            attempted=True,
            reason="Validated exact-mapping syllabus was published and activated in-process.",
            generation_id=publication.generation_id,
            stop_reason=probe.get("stop_reason"),
            browser_response_count=int(probe.get("actual_observed_responses", 0)),
            essential_request_count=int(probe.get("essential_document_requests", 0)),
            diagnostic_id=diagnostic_id,
            **scoped,
        )


_coordinator_guard = threading.Lock()
_coordinators: dict[tuple[Any, ...], SyllabusAcquisitionCoordinator] = {}


def get_syllabus_acquisition_coordinator(settings: SyllabusAcquisitionSettings) -> SyllabusAcquisitionCoordinator:
    key = settings.key()
    with _coordinator_guard:
        coordinator = _coordinators.get(key)
        if coordinator is None:
            coordinator = SyllabusAcquisitionCoordinator(settings)
            _coordinators[key] = coordinator
        return coordinator


def clear_syllabus_acquisition_coordinators() -> None:
    with _coordinator_guard:
        _coordinators.clear()
