"""Retention decisions per class, tombstones, and applied runs."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.service import layout, manifests, retention
from app.types import SessionCreate

TODAY = date(2026, 11, 19)


def _manifest(session_class: str, ended_days_ago: float, status: str = "processed"):
    ended = datetime(2026, 11, 19, 12, 0, tzinfo=UTC) - timedelta(days=ended_days_ago)
    sid = layout.new_session_id(ended)
    manifest = manifests.new_manifest(
        sid, SessionCreate(script_id="order-status", session_class=session_class), ended
    )
    manifest.status = status
    manifest.egress.ended_at = ended
    manifest.recording.size_bytes = 10
    return manifest


@pytest.mark.parametrize(
    ("session_class", "days_ago", "expected"),
    [
        ("debug", 0, "keep"),  # retain_until is tomorrow noon
        ("debug", 1, "remove"),  # retain_until falls on the as-of date
        ("debug", 3, "remove"),
        ("standard", 29, "keep"),
        ("standard", 31, "remove"),
        ("training", 364, "keep"),
        ("training", 366, "remove"),
        ("hold", 5000, "keep"),
    ],
)
def test_decision_per_class(session_class, days_ago, expected):
    assert retention.decide(_manifest(session_class, days_ago), TODAY) == expected


def test_expired_manifests_stay_tombstones():
    assert retention.decide(_manifest("debug", 10, status="expired"), TODAY) == "expired"


def test_in_progress_recording_is_never_removed():
    assert retention.decide(_manifest("debug", 10, status="recording"), TODAY) == "keep"


def test_overrides_come_from_settings(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "retention_days_standard", 7)
    assert retention.decide(_manifest("standard", 8), TODAY) == "remove"
    assert retention.policy().classes[1].retain_days == 7
    assert retention.policy().classes[3].retain_days is None


def _seed(store, manifest):
    sid = manifest.session_id
    store.put_bytes(layout.recording_key(sid), b"0123456789", "audio/ogg")
    store.put_json(layout.transcript_key(sid), {"text": "x"})
    store.put_json(layout.evaluation_key(sid), {"wer": 0})
    store.put_json(layout.webhook_key(sid, "EV_1"), {"event": "egress_ended"})
    manifests.save(manifest)
    return sid


def test_dry_run_changes_nothing(store):
    sid = _seed(store, _manifest("debug", 3))
    before = {k: list(v) for k, v in store.versions.items()}
    report = retention.run(as_of=TODAY, dry_run=True)
    assert report.removed_total == 1 and report.report_key is None
    assert store.versions == before
    assert sid in report.classes[0].removed


def test_applied_run_removes_media_keeps_manifest_and_writes_report(store):
    removed = _seed(store, _manifest("debug", 3))
    kept = _seed(store, _manifest("standard", 3))
    held = _seed(store, _manifest("hold", 900))

    report = retention.run(as_of=TODAY, dry_run=False)

    assert report.removed_total == 1 and report.kept_total == 2
    assert report.removed_bytes > 0
    assert store.head(layout.recording_key(removed)) is None
    assert store.head(layout.transcript_key(removed)) is None
    assert store.head(layout.webhook_key(removed, "EV_1")) is not None
    tombstone = store.json(layout.manifest_key(removed))
    assert tombstone["status"] == "expired" and tombstone["retention"]["removed_at"]
    for sid in (kept, held):
        assert store.head(layout.recording_key(sid)) is not None

    stored = store.json(layout.report_key("2026-11-19"))
    assert stored["removed_total"] == 1
    assert retention.list_reports().items[0].date == "2026-11-19"

    again = retention.run(as_of=TODAY, dry_run=False)
    assert again.removed_total == 0
    assert again.classes[0].already_expired == [removed]


@pytest.mark.asyncio
async def test_retention_routes(client, store):
    _seed(store, _manifest("debug", 3))
    policy = (await client.get("/api/retention/policy")).json()
    assert [c["session_class"] for c in policy["classes"]] == ["debug", "standard", "training", "hold"]
    run = await client.post("/api/retention/runs", json={"as_of": "2026-11-19"})
    assert run.status_code == 200 and run.json()["dry_run"] is True
    assert (await client.get("/api/retention/reports")).json()["items"] == []
    applied = await client.post("/api/retention/runs", json={"as_of": "2026-11-19", "dry_run": False})
    assert applied.json()["report_key"].endswith("reports/2026-11-19.json")
    assert (await client.get("/api/retention/reports/2026-11-19")).status_code == 200
    assert (await client.get("/api/retention/reports/2026-01-01")).status_code == 404
    assert (await client.get("/api/retention/reports/bad")).status_code == 400
