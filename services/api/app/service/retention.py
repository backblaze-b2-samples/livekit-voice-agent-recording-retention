"""Retention by session class.

A session is removed when its `retain_until` falls on or before the as-of date
(UTC). Removal deletes every version of the recording, transcript and
evaluation, then rewrites the manifest as an `expired` tombstone with
`retention.removed_at`. The manifest and the webhook evidence are never removed
by retention; `hold` sessions are never removed.

A dry run (the default) returns the report without deleting or writing
anything. An applied run writes `reports/<as_of>.json`.
"""

import logging
from datetime import UTC, date, datetime

from app.config import settings
from app.repo import session_store
from app.service import layout, manifests
from app.service.sessions import all_manifests
from app.types import (
    ClassPolicy,
    RetentionClassResult,
    RetentionPolicy,
    RetentionReport,
    RetentionReportList,
    RetentionReportSummary,
    SessionManifest,
)
from app.types.sessions import SESSION_CLASSES

logger = logging.getLogger(__name__)

# Removed by retention. Everything else under the session prefix stays.
REMOVABLE = (layout.RECORDING, layout.TRANSCRIPT, layout.EVALUATION)


def policy() -> RetentionPolicy:
    days = settings.retention_days
    return RetentionPolicy(
        classes=[ClassPolicy(session_class=c, retain_days=days[c]) for c in SESSION_CLASSES]  # type: ignore[arg-type]
    )


def decide(manifest: SessionManifest, as_of: date) -> str:
    """'expired' (already a tombstone), 'remove', or 'keep'. Pure."""
    if manifest.status == "expired":
        return "expired"
    days = settings.retention_days.get(manifest.session_class)
    if days is None:
        return "keep"
    retain_until = manifests.retention_for(
        manifest.session_class, manifests.retention_anchor(manifest)
    ).retain_until
    if manifest.status == "recording" or retain_until is None:
        return "keep"
    return "remove" if retain_until.date() <= as_of else "keep"


def _expire(manifest: SessionManifest, now: datetime) -> int:
    prefix = layout.session_prefix(manifest.session_id)
    freed = 0
    for name in REMOVABLE:
        _, size = session_store.delete_all_versions(prefix + name)
        freed += size
    with manifests.session_lock(manifest.session_id):
        current = manifests.load(manifest.session_id) or manifest
        current.status = "expired"
        current.retention.removed_at = now
        manifests.save(current)
    return freed


def run(as_of: date | None = None, dry_run: bool = True) -> RetentionReport:
    now = datetime.now(UTC)
    as_of = as_of or now.date()
    buckets = {
        c: {"kept": [], "removed": [], "already_expired": []} for c in SESSION_CLASSES
    }
    removed_bytes = 0
    for manifest in all_manifests():
        decision = decide(manifest, as_of)
        bucket = buckets[manifest.session_class]
        if decision == "expired":
            bucket["already_expired"].append(manifest.session_id)
        elif decision == "keep":
            bucket["kept"].append(manifest.session_id)
        else:
            bucket["removed"].append(manifest.session_id)
            if dry_run:
                removed_bytes += manifest.recording.size_bytes or 0
            else:
                removed_bytes += _expire(manifest, now)

    days = settings.retention_days
    report = RetentionReport(
        date=as_of.isoformat(),
        as_of=as_of,
        generated_at=now,
        dry_run=dry_run,
        report_key=None if dry_run else layout.report_key(as_of.isoformat()),
        classes=[
            RetentionClassResult(session_class=c, retain_days=days[c], **buckets[c])  # type: ignore[arg-type]
            for c in SESSION_CLASSES
        ],
        kept_total=sum(len(b["kept"]) for b in buckets.values()),
        removed_total=sum(len(b["removed"]) for b in buckets.values()),
        removed_bytes=removed_bytes,
    )
    if not dry_run:
        session_store.put_json(layout.report_key(report.date), report.model_dump(mode="json"))
    logger.info(
        "Retention %s as_of=%s removed=%d kept=%d",
        "dry run" if dry_run else "applied",
        as_of,
        report.removed_total,
        report.kept_total,
    )
    return report


def list_reports() -> RetentionReportList:
    items = []
    for obj in session_store.list_objects(layout.reports_root()):
        key = obj["Key"]
        if not key.endswith(".json"):
            continue
        data = session_store.get_json(key) or {}
        items.append(
            RetentionReportSummary(
                date=key.rsplit("/", 1)[-1].removesuffix(".json"),
                key=key,
                kept_total=int(data.get("kept_total", 0)),
                removed_total=int(data.get("removed_total", 0)),
                generated_at=data.get("generated_at"),
            )
        )
    return RetentionReportList(items=sorted(items, key=lambda r: r.date, reverse=True))


def get_report(day: str) -> RetentionReport | None:
    data = session_store.get_json(layout.report_key(day))
    return RetentionReport.model_validate(data) if data else None
