"""Webhook receiver: real LiveKit signatures, tamper rejection, dedupe, manifest updates."""

import base64
import hashlib
from datetime import UTC, datetime

import pytest
from google.protobuf.json_format import MessageToJson
from livekit import api as lk

from app.runtime import webhooks as webhooks_runtime
from app.service import layout, manifests
from app.types import SessionCreate

SID = "s-20261119-a1b2c3"
STARTED_NS = 1_763_542_800_000_000_000
ENDED_NS = STARTED_NS + 21_400_000_000


def _sign(body: str, settings) -> str:
    digest = base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
    return (
        lk.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_sha256(digest)
        .to_jwt()
    )


def _event(event: str, event_id: str, status=lk.EgressStatus.EGRESS_COMPLETE, files=True) -> str:
    info = lk.EgressInfo(
        egress_id="EG_test",
        room_name=SID,
        status=status,
        started_at=STARTED_NS,
        ended_at=ENDED_NS if event == "egress_ended" else 0,
    )
    if files and event == "egress_ended":
        info.file_results.append(
            lk.FileInfo(
                filename=layout.recording_key(SID),
                location=f"https://example.invalid/bucket/{layout.recording_key(SID)}",
                size=48_213,
                duration=21_400_000_000,
            )
        )
    return MessageToJson(
        lk.WebhookEvent(event=event, id=event_id, created_at=1_763_542_830, egress_info=info)
    )


@pytest.fixture
def session(store):
    now = datetime(2026, 11, 19, 9, 0, tzinfo=UTC)
    manifest = manifests.new_manifest(SID, SessionCreate(script_id="support-handoff"), now)
    manifests.save(manifest)
    return manifest


@pytest.fixture
def processed(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(webhooks_runtime.postprocess, "process_session", calls.append)
    return calls


async def _post(client, body: str, auth: str | None):
    headers = {"Content-Type": "application/webhook+json"}
    if auth is not None:
        headers["Authorization"] = auth
    return await client.post("/api/webhooks/livekit", content=body, headers=headers)


@pytest.mark.asyncio
async def test_signed_egress_ended_updates_manifest_and_stores_evidence(
    client, lk_keys, store, session, processed
):
    body = _event("egress_ended", "EV_end_1")
    response = await _post(client, body, _sign(body, lk_keys))

    assert response.status_code == 200
    assert response.json() == {"received": True, "event": "egress_ended", "duplicate": False}
    manifest = store.json(layout.manifest_key(SID))
    assert manifest["status"] == "recorded"
    assert manifest["egress"]["status"] == "EGRESS_COMPLETE"
    assert manifest["egress"]["webhook"]["event_id"] == "EV_end_1"
    assert manifest["recording"]["size_bytes"] == 48_213
    assert manifest["recording"]["duration_s"] == 21.4
    assert manifest["recording"]["location"].endswith(layout.recording_key(SID))
    # The raw verified body is the evidence, byte for byte.
    assert store.versions[layout.webhook_key(SID, "EV_end_1")][-1] == body.encode()
    assert processed == [SID]


@pytest.mark.asyncio
async def test_tampered_body_is_rejected(client, lk_keys, store, session, processed):
    body = _event("egress_ended", "EV_end_2")
    auth = _sign(body, lk_keys)
    tampered = body.replace("48213", "1")
    response = await _post(client, tampered, auth)

    assert response.status_code == 401
    assert store.json(layout.manifest_key(SID))["status"] == "recording"
    assert processed == []


@pytest.mark.asyncio
async def test_unsigned_and_wrong_key_are_rejected(client, lk_keys, store, session):
    body = _event("egress_started", "EV_start_x")
    assert (await _post(client, body, None)).status_code == 401
    forged = (
        lk.AccessToken("devkey", "some-other-secret-0123456789abcdef")
        .with_sha256(base64.b64encode(hashlib.sha256(body.encode()).digest()).decode())
        .to_jwt()
    )
    assert (await _post(client, body, forged)).status_code == 401


@pytest.mark.asyncio
async def test_retried_event_is_deduplicated(client, lk_keys, store, session, processed):
    body = _event("egress_ended", "EV_end_3")
    auth = _sign(body, lk_keys)
    first = await _post(client, body, auth)
    second = await _post(client, body, auth)

    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True
    assert len(store.versions[layout.webhook_key(SID, "EV_end_3")]) == 1
    assert processed == [SID]


@pytest.mark.asyncio
async def test_dedupe_survives_restart_via_evidence_in_b2(
    client, lk_keys, store, session, processed
):
    from app.service import webhooks

    body = _event("egress_ended", "EV_end_4")
    auth = _sign(body, lk_keys)
    await _post(client, body, auth)
    webhooks._reset_state()  # simulate an API restart: in-memory ids are gone
    again = await _post(client, body, auth)
    assert again.json()["duplicate"] is True


@pytest.mark.asyncio
async def test_failed_egress_marks_session_failed(client, lk_keys, store, session, processed):
    body = _event("egress_ended", "EV_end_5", status=lk.EgressStatus.EGRESS_FAILED, files=False)
    response = await _post(client, body, _sign(body, lk_keys))
    assert response.status_code == 200
    assert store.json(layout.manifest_key(SID))["status"] == "failed"
    assert processed == []


@pytest.mark.asyncio
async def test_rooms_this_app_did_not_create_are_ignored(client, lk_keys, store, processed):
    body = MessageToJson(
        lk.WebhookEvent(event="room_finished", id="EV_room", room=lk.Room(name="someone-else"))
    )
    response = await _post(client, body, _sign(body, lk_keys))
    assert response.status_code == 200
    assert store.keys() == []
