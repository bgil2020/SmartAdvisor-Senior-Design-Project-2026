"""Sanitized browser-request diagnostics for bounded syllabus collection."""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qsl, urlparse

DIAGNOSTIC_SCHEMA_VERSION = "1.0"
APPROVED_HOST = "fau.simplesyllabus.com"
_SAFE_STATIC_SEGMENTS = {
    "api", "api2", "assets", "doc", "document", "en-US", "locale-redirect",
    "robots.txt", "syllabus", "ui",
}
_URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_EMAIL_PATTERN = re.compile(r"\b[^\s@]+@[^\s@]+\b")
_WINDOWS_PATH_PATTERN = re.compile(r"\b[A-Za-z]:\\[^\r\n]+")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def approved_document_path(path: str, document_id: str) -> bool:
    """Allow the tracked document path with an optional ordinary locale prefix."""
    return path.startswith(f"/doc/{document_id}/") or path.startswith(f"/en-US/doc/{document_id}/")


def _fingerprint(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:length]


def sanitize_url(url: str, *, document_id: str, expected_url: str) -> dict[str, Any]:
    """Return endpoint diagnostics without query values, credentials, or fragments."""
    parsed = urlparse(url)
    expected = urlparse(expected_url)
    host = (parsed.hostname or "").lower()
    path = parsed.path or "/"
    if host == APPROVED_HOST and approved_document_path(path, document_id):
        safe_path = path
    else:
        safe_segments: list[str] = []
        for segment in path.split("/"):
            if not segment:
                continue
            if segment in _SAFE_STATIC_SEGMENTS or segment == document_id:
                safe_segments.append(segment)
            else:
                suffix = Path(segment).suffix if "." in segment else ""
                label = "asset" if suffix in {".css", ".gif", ".ico", ".js", ".json", ".png", ".svg", ".woff", ".woff2"} else "segment"
                safe_segments.append(f"<{label}:{_fingerprint(segment, 10)}>{suffix if label == 'asset' else ''}")
        safe_path = "/" + "/".join(safe_segments)
    query_keys = sorted({key[:64] for key, _ in parse_qsl(parsed.query, keep_blank_values=True)})
    canonical = f"{parsed.scheme.lower()}://{host}{safe_path}?{'&'.join(query_keys)}"
    return {
        "scheme": parsed.scheme.lower(),
        "host": host,
        "approved_host": host == APPROVED_HOST,
        "expected_document_path": host == APPROVED_HOST and approved_document_path(path, document_id),
        "path": safe_path,
        "query_keys": query_keys,
        "url_fingerprint": _fingerprint(canonical),
        "matches_literal_expected_url": url == expected_url,
        "matches_expected_origin": (parsed.scheme.lower(), host) == (expected.scheme.lower(), (expected.hostname or "").lower()),
    }


def sanitize_error_summary(value: Any, *, limit: int = 180) -> str:
    """Bound and redact browser errors without retaining source content or paths."""
    text = str(value or "")
    text = _URL_PATTERN.sub("<url>", text)
    text = _EMAIL_PATTERN.sub("<email>", text)
    text = _WINDOWS_PATH_PATTERN.sub("<local-path>", text)
    text = re.sub(r"([?&][A-Za-z0-9_.-]{1,64}=)[^&\s]+", r"\1<redacted>", text)
    text = " ".join(text.split())
    return text[:limit]


def classify_response_details(url: str, status: int, resource_type: str, document_id: str) -> tuple[str, str]:
    """Explain the existing conservative response classification."""
    lower = url.casefold()
    if any(token in lower for token in ("sentry", "analytics", "telemetry", "google-analytics")):
        return "telemetry", "known_telemetry_endpoint"
    same_host = urlparse(url).hostname == APPROVED_HOST
    document_capable = resource_type in {"document", "xhr", "fetch"}
    if same_host and document_capable and document_id in url:
        return "essential_document", "approved_host_document_identity"
    if same_host and document_capable and status in {401, 403}:
        return "essential_document", "approved_host_auth_denial_on_document_capable_request"
    return "other", "not_document_identity_or_auth_denial"


def request_ownership(request: Any, *, main_frame: Any) -> str:
    """Describe request ownership without assuming ``request.frame`` is available."""
    try:
        if getattr(request, "service_worker", None) is not None:
            return "service_worker"
    except Exception:
        return "service_worker_unknown"
    try:
        frame = request.frame
    except Exception:
        return "navigation_without_frame" if request.is_navigation_request() else "frame_unavailable"
    return "main_frame" if frame == main_frame else "subframe"


class SanitizedBrowserDiagnostics:
    """Collect a bounded request lifecycle without headers, bodies, or raw URLs."""

    def __init__(
        self,
        *,
        destination: Path,
        diagnostic_id: str,
        document_id: str,
        expected_url: str,
        launch: dict[str, Any],
        now: Callable[[], str] = utc_now,
        event_limit: int = 240,
    ):
        self.destination = destination
        self.diagnostic_id = diagnostic_id
        self.document_id = document_id
        self.expected_url = expected_url
        self.launch = launch
        self.now = now
        self.event_limit = event_limit
        self.events: list[dict[str, Any]] = []
        self._request_ids: dict[int, str] = {}
        self._requests: dict[int, Any] = {}
        self._seen_response_keys: set[tuple[int, int]] = set()
        self._dropped_events = False
        self._written = False

    def _append(self, event: dict[str, Any]) -> None:
        if len(self.events) < self.event_limit:
            self.events.append({"timestamp": self.now(), **event})
        else:
            self._dropped_events = True

    def request_id(self, request: Any) -> str:
        key = id(request)
        if self._requests.get(key) is not request:
            self._requests[key] = request
            self._request_ids[key] = f"request-{len(self._request_ids) + 1:03d}"
        return self._request_ids[key]

    def request_record(self, request: Any, *, main_frame: Any) -> dict[str, Any]:
        redirected = getattr(request, "redirected_from", None)
        return {
            "request_id": self.request_id(request),
            "redirected_from_request_id": self.request_id(redirected) if redirected is not None else None,
            "method": str(getattr(request, "method", "UNKNOWN"))[:16],
            "resource_type": str(getattr(request, "resource_type", "unknown"))[:32],
            "is_navigation": bool(request.is_navigation_request()),
            "ownership": request_ownership(request, main_frame=main_frame),
            "endpoint": sanitize_url(str(getattr(request, "url", "")), document_id=self.document_id, expected_url=self.expected_url),
        }

    def record_route(self, request: Any, *, main_frame: Any, action: str, completed: bool, error: Any = None) -> None:
        self._append({
            "kind": "route",
            **self.request_record(request, main_frame=main_frame),
            "route_action": action,
            "route_completed": completed,
            "error": sanitize_error_summary(error) if error else None,
        })

    def record_response(self, response: Any, *, main_frame: Any) -> dict[str, Any] | None:
        request = response.request
        status = int(response.status)
        response_key = (id(request), status)
        if response_key in self._seen_response_keys:
            return None
        self._seen_response_keys.add(response_key)
        resource_type = str(getattr(request, "resource_type", "unknown"))
        role, reason = classify_response_details(str(request.url), status, resource_type, self.document_id)
        try:
            content_type = response.header_value("content-type")
        except Exception:
            content_type = None
        event = {
            "kind": "response",
            **self.request_record(request, main_frame=main_frame),
            "status": status,
            "role": role,
            "classification_reason": reason,
            "content_type": sanitize_error_summary(content_type, limit=96) if content_type else None,
            "from_service_worker": bool(getattr(response, "from_service_worker", False)),
        }
        self._append(event)
        return event

    def record_request_failure(self, request: Any, *, main_frame: Any) -> None:
        self._append({
            "kind": "request_failed",
            **self.request_record(request, main_frame=main_frame),
            "failure": sanitize_error_summary(getattr(request, "failure", None)),
        })

    def record_browser_error(self, kind: str, error: Any) -> None:
        self._append({"kind": kind, "error": sanitize_error_summary(error)})

    def write(self) -> None:
        if self._written:
            return
        self._written = True
        payload = {
            "schema_version": DIAGNOSTIC_SCHEMA_VERSION,
            "diagnostic_id": self.diagnostic_id,
            "created_at": self.now(),
            "source": sanitize_url(self.expected_url, document_id=self.document_id, expected_url=self.expected_url),
            "launch": self.launch,
            "event_limit": self.event_limit,
            "events_truncated": self._dropped_events,
            "events": self.events,
        }
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.destination.with_name(f".{self.destination.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("x", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.destination)
        finally:
            temporary.unlink(missing_ok=True)
