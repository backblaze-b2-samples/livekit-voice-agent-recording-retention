"""Manifest construction, persistence and per-session serialization.

Invariant: every session has a `manifest.json` from the moment it is created.
Retention never deletes it; only an explicit user delete removes a session.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from threading import Lock

from app.config import settings
from app.repo import session_store
from app.service import layout
from app.types import SessionCreate, SessionManifest, SessionSummary
from app.types.sessions import RecordingInfo, RetentionInfo

_locks: dict[str, Lock] = {}
_locks_guard = Lock()


@contextmanager
def session_lock(session_id: str) -> Iterator[None]:
    """Serialize read-modify-write cycles on one manifest within this process.

    Egress start/end webhooks, post-processing and user edits can all touch the
    same manifest within a second; without this the last writer would silently
    drop the others' fields.
    """
    with _locks_guard:
        lock = _locks.setdefault(session_id, Lock())
    with lock:
        yield


def retention_for(session_class: str, anchor: datetime) -> RetentionInfo:
    """Retain-until is anchored on the recording's end (or creation, before that)."""
    days = settings.retention_days.get(session_class)
    return RetentionInfo(
        session_class=session_class,  # type: ignore[arg-type]
        retain_days=days,
        retain_until=None if days is None else anchor + timedelta(days=days),
    )


def retention_anchor(manifest: SessionManifest) -> datetime:
    return manifest.egress.ended_at or manifest.created_at


def new_manifest(session_id: str, request: SessionCreate, now: datetime) -> SessionManifest:
    return SessionManifest(
        session_id=session_id,
        date=layout.session_date(session_id),
        session_class=request.session_class,
        script_id=request.script_id,
        mode=request.mode,
        label=request.label,
        status="recording",
        created_at=now,
        recording=RecordingInfo(key=layout.recording_key(session_id)),
        retention=retention_for(request.session_class, now),
    )


def load(session_id: str) -> SessionManifest | None:
    data = session_store.get_json(layout.manifest_key(session_id))
    return SessionManifest.model_validate(data) if data else None


def save(manifest: SessionManifest) -> None:
    session_store.put_json(
        layout.manifest_key(manifest.session_id), manifest.model_dump(mode="json")
    )


def list_manifest_keys() -> list[str]:
    """Manifest keys under `sessions/`, newest session first."""
    keys = [
        obj["Key"]
        for obj in session_store.list_objects(layout.sessions_root())
        if layout.session_id_from_key(obj["Key"])
    ]
    return sorted(keys, key=lambda k: layout.session_id_from_key(k) or "", reverse=True)


def summary(manifest: SessionManifest) -> SessionSummary:
    return SessionSummary(
        session_id=manifest.session_id,
        date=manifest.date,
        session_class=manifest.session_class,
        script_id=manifest.script_id,
        mode=manifest.mode,
        label=manifest.label,
        status=manifest.status,
        created_at=manifest.created_at,
        duration_s=manifest.recording.duration_s,
        size_bytes=manifest.recording.size_bytes,
        wer=manifest.evaluation.wer if manifest.evaluation else None,
        passed=manifest.evaluation.passed if manifest.evaluation else None,
        retain_until=manifest.retention.retain_until,
    )


def utcnow() -> datetime:
    return datetime.now(UTC)


def ns_to_datetime(value: int) -> datetime | None:
    return datetime.fromtimestamp(value / 1e9, tz=UTC) if value else None


def ns_to_seconds(value: int | str | None) -> float | None:
    """Egress durations are int64 nanoseconds; protobuf JSON serializes them as strings."""
    if value in (None, "", 0, "0"):
        return None
    return round(int(value) / 1e9, 3)
