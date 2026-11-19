"""Dashboard figures, computed from the session manifests in B2."""

from collections import Counter

from app.service import manifests
from app.service.retention import list_reports
from app.service.sessions import all_manifests
from app.types import ArchiveStats, CountBucket
from app.types.formatting import humanize_bytes
from app.types.sessions import SESSION_CLASSES, SESSION_STATUSES


def archive_stats(recent: int = 5) -> ArchiveStats:
    sessions = all_manifests()
    by_class = Counter(m.session_class for m in sessions)
    by_status = Counter(m.status for m in sessions)
    live = [m for m in sessions if m.status != "expired"]
    seconds = sum(m.recording.duration_s or 0.0 for m in live)
    size = sum(m.recording.size_bytes or 0 for m in live)
    reports = list_reports().items
    return ArchiveStats(
        total_sessions=len(sessions),
        by_class=[CountBucket(name=c, count=by_class.get(c, 0)) for c in SESSION_CLASSES],
        by_status=[CountBucket(name=s, count=by_status.get(s, 0)) for s in SESSION_STATUSES],
        recorded_seconds=round(seconds, 1),
        recorded_bytes=size,
        recorded_bytes_human=humanize_bytes(size),
        passed_evaluations=sum(1 for m in sessions if m.evaluation and m.evaluation.passed),
        last_report=reports[0] if reports else None,
        recent_sessions=[manifests.summary(m) for m in sessions[:recent]],
    )
