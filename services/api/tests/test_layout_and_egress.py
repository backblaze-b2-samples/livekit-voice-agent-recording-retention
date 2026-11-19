"""Key layout and Egress request construction (pure, no network)."""

from datetime import UTC, datetime

import pytest
from livekit import api as lk

from app.repo import livekit_api
from app.service import layout, manifests


def test_session_id_and_date_segment():
    sid = layout.new_session_id(datetime(2026, 11, 19, 8, 0, tzinfo=UTC))
    assert layout.SESSION_ID_RE.match(sid)
    assert layout.session_date(sid) == "2026-11-19"


@pytest.mark.parametrize("bad", ["", "s-2026-ab", "../s-20261119-a1b2c3", "s-20261119-A1B2C3"])
def test_invalid_session_ids_are_rejected(bad):
    with pytest.raises(layout.InvalidSessionId):
        layout.session_date(bad)


def test_keys_live_under_archive_prefix(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "archive_prefix", "e2e/run-1/")
    sid = "s-20261119-a1b2c3"
    assert layout.recording_key(sid) == "e2e/run-1/sessions/2026-11-19/s-20261119-a1b2c3/recording.ogg"
    assert layout.manifest_key(sid).endswith("/s-20261119-a1b2c3/manifest.json")
    assert layout.webhook_key(sid, "EV_a/b") .endswith("/webhooks/EV_a_b.json")
    assert layout.report_key("2026-11-19") == "e2e/run-1/reports/2026-11-19.json"
    assert layout.session_id_from_key(layout.manifest_key(sid)) == sid
    assert layout.session_id_from_key(layout.recording_key(sid)) is None


def test_egress_request_targets_b2_endpoint_from_region(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "b2_region", "example-region-9")
    monkeypatch.setattr(settings, "b2_bucket_name", "archive-bucket")
    monkeypatch.setattr(settings, "b2_application_key_id", "test-key-id")
    monkeypatch.setattr(settings, "b2_application_key", "test-app-key")
    monkeypatch.setattr(settings, "archive_prefix", "e2e/run-2/")
    sid = "s-20261119-a1b2c3"

    request = livekit_api.build_egress_request(sid, layout.recording_key(sid))

    assert request.room_name == sid
    assert request.audio_only is True
    (output,) = request.file_outputs
    assert output.file_type == lk.EncodedFileType.OGG
    # A literal key: no {room_name}/{time} templates, so the location is known up front.
    assert output.filepath == "e2e/run-2/sessions/2026-11-19/s-20261119-a1b2c3/recording.ogg"
    assert "{" not in output.filepath
    s3 = output.s3
    assert s3.endpoint == "https://s3.example-region-9.backblazeb2.com"
    assert s3.region == "example-region-9"
    assert s3.bucket == "archive-bucket"
    assert s3.access_key == "test-key-id"
    assert s3.metadata["source"] == "b2ai-livekit-agent-session-archive"


@pytest.mark.parametrize(
    ("value", "expected"),
    [(12_500_000_000, 12.5), ("12500000000", 12.5), ("0", None), (None, None), (1, 0.0)],
)
def test_egress_duration_nanoseconds_to_seconds(value, expected):
    assert manifests.ns_to_seconds(value) == expected
