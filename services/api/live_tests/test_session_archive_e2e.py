"""Live end-to-end suite (`make test`). Real LiveKit, real Egress, real B2.

Runs inside the api container with ARCHIVE_PREFIX=e2e/<run-id>/, so the session,
the retention fixtures and the report all live under that prefix, and the
prefix is deleted (every version) at the end. Opt-in: RUN_LIVE_SESSION_TESTS=1.
"""

import os
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from app.config import settings
from app.repo import session_store
from app.service import layout, manifests
from app.types import SessionCreate
from live_tests.session_client import client, create_scripted_session, wait_for_terminal

pytestmark = pytest.mark.live

if os.environ.get("RUN_LIVE_SESSION_TESTS") != "1":
    pytest.skip("set RUN_LIVE_SESSION_TESTS=1 (make test does)", allow_module_level=True)


def measured_duration_s(path: Path) -> float:
    """Decode every audio frame with PyAV and add up the samples."""
    import av

    samples = 0
    rate = 0
    with av.open(str(path)) as container:
        stream = container.streams.audio[0]
        for frame in container.decode(stream):
            samples += frame.samples
            rate = frame.sample_rate
    assert rate, "no audio frames decoded"
    return samples / rate


@pytest.fixture(scope="module", autouse=True)
def isolated_prefix():
    prefix = settings.archive_prefix
    assert prefix.startswith("e2e/") and prefix.endswith("/"), (
        "the live suite only runs under an e2e/<run-id>/ ARCHIVE_PREFIX (make test sets it)"
    )
    yield prefix
    session_store.delete_all_versions(prefix)


@pytest.fixture(scope="module")
def http():
    with client() as c:
        yield c


@pytest.fixture(scope="module")
def processed_session(http):
    created = create_scripted_session(http, session_class="standard")
    assert created["status"] == "recording"
    # Manifest-first invariant: it exists before anything has been recorded.
    assert session_store.get_json(layout.manifest_key(created["session_id"])) is not None
    return wait_for_terminal(http, created["session_id"])


def test_session_is_processed(processed_session):
    manifest = processed_session["manifest"]
    assert manifest["status"] == "processed", manifest.get("error")


def test_webhook_delivered_and_evidence_stored(processed_session):
    manifest = processed_session["manifest"]
    webhook = manifest["egress"]["webhook"]
    assert webhook["event"] == "egress_ended"
    assert manifest["egress"]["status"] == "EGRESS_COMPLETE"
    evidence = session_store.get_json(webhook["evidence_key"])
    assert evidence is not None and evidence["event"] == "egress_ended"


def test_recording_location_checksum_size_and_duration(processed_session):
    recording = processed_session["manifest"]["recording"]
    key = recording["key"]
    assert key == layout.recording_key(processed_session["manifest"]["session_id"])
    assert recording["location"].endswith(key)

    head = session_store.head(key)
    assert head is not None
    assert recording["size_bytes"] == head["size"]

    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / "recording.ogg"
        session_store.download_to(key, local)
        import hashlib

        assert hashlib.sha256(local.read_bytes()).hexdigest() == recording["sha256"]
        assert abs(measured_duration_s(local) - recording["duration_s"]) <= 1.0


def test_transcription_and_evaluation(processed_session):
    manifest = processed_session["manifest"]
    assert manifest["transcription"]["word_count"] > 0
    assert session_store.get_json(manifest["transcription"]["key"]) is not None
    assert session_store.get_json(manifest["evaluation"]["key"]) is not None
    assert manifest["evaluation"]["passed"], processed_session.get("evaluation")


def _seed(session_class: str, ended_days_ago: int, today: date) -> str:
    ended = datetime.combine(today, datetime.min.time(), tzinfo=UTC) - timedelta(
        days=ended_days_ago
    ) + timedelta(hours=12)
    session_id = layout.new_session_id(ended)
    manifest = manifests.new_manifest(
        session_id,
        SessionCreate(script_id="order-status", session_class=session_class, label="retention fixture"),
        ended - timedelta(minutes=1),
    )
    manifest.status = "processed"
    manifest.egress.status = "EGRESS_COMPLETE"
    manifest.egress.ended_at = ended
    manifest.recording.size_bytes = 16
    manifest.retention = manifests.retention_for(session_class, ended)
    session_store.put_bytes(manifest.recording.key, b"placeholder-ogg!", "audio/ogg")
    session_store.put_json(layout.transcript_key(session_id), {"text": "fixture"})
    manifests.save(manifest)
    return session_id


def test_retention_by_class(http, processed_session):
    today = datetime.now(UTC).date()
    removed = {
        _seed("debug", 3, today),
        _seed("standard", 45, today),
        _seed("training", 400, today),
    }
    kept = {
        _seed("standard", 5, today),
        _seed("training", 30, today),
        _seed("hold", 1000, today),
        processed_session["manifest"]["session_id"],
    }

    response = http.post(
        "/api/retention/runs", json={"as_of": today.isoformat(), "dry_run": False}
    )
    response.raise_for_status()
    report = response.json()

    reported_removed = {sid for c in report["classes"] for sid in c["removed"]}
    reported_kept = {sid for c in report["classes"] for sid in c["kept"]}
    assert reported_removed == removed
    assert kept <= reported_kept

    for session_id in removed:
        manifest = session_store.get_json(layout.manifest_key(session_id))
        assert manifest["status"] == "expired"
        assert manifest["retention"]["removed_at"]
        assert session_store.head(layout.recording_key(session_id)) is None
        assert session_store.head(layout.transcript_key(session_id)) is None
    for session_id in kept:
        assert session_store.head(layout.recording_key(session_id)) is not None

    stored = session_store.get_json(layout.report_key(today.isoformat()))
    assert stored is not None
    assert stored["classes"] == report["classes"]
    fetched = http.get(f"/api/retention/reports/{today.isoformat()}").json()
    assert fetched["removed_total"] == len(removed)
