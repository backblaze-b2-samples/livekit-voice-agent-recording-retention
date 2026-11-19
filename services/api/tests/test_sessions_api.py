"""Session lifecycle through the HTTP API, with LiveKit and B2 stubbed at repo/."""

import pytest

from app.service import layout
from app.service import sessions as sessions_service


@pytest.mark.asyncio
async def test_scripts_are_listed(client):
    response = await client.get("/api/scripts")
    ids = [s["id"] for s in response.json()["items"]]
    assert "support-handoff" in ids
    first = response.json()["items"][0]
    assert first["line_count"] > 0 and first["expected_duration_s"] > 0


@pytest.mark.asyncio
async def test_create_writes_manifest_before_egress(client, store, livekit, monkeypatch):
    manifest_at_egress_start: list[bool] = []
    original = livekit.start_egress

    def checking_start(room_name, filepath):
        manifest_at_egress_start.append(store.get_json(layout.manifest_key(room_name)) is not None)
        return original(room_name, filepath)

    from app.repo import livekit_api

    monkeypatch.setattr(livekit_api, "start_egress", checking_start)
    response = await client.post(
        "/api/sessions",
        json={"script_id": "support-handoff", "session_class": "debug", "mode": "scripted"},
    )

    assert response.status_code == 201
    body = response.json()
    sid = body["session_id"]
    assert layout.SESSION_ID_RE.match(sid)
    assert body["status"] == "recording"
    assert body["egress"]["egress_id"] == "EG_test"
    assert body["retention"]["retain_days"] == 1
    assert livekit.names() == ["create_room", "dispatch_agent", "start_egress"]
    assert livekit.calls[2][2] == layout.recording_key(sid)
    assert manifest_at_egress_start == [True]
    assert store.json(layout.manifest_key(sid))["egress"]["egress_id"] == "EG_test"


@pytest.mark.asyncio
async def test_unknown_script_is_400_and_creates_nothing(client, store, livekit):
    response = await client.post("/api/sessions", json={"script_id": "nope"})
    assert response.status_code == 400
    assert livekit.calls == [] and store.keys() == []


@pytest.mark.asyncio
async def test_failed_egress_start_keeps_a_failed_manifest(client, store, livekit):
    livekit.fail_on = "start_egress"
    response = await client.post("/api/sessions", json={"script_id": "support-handoff"})
    assert response.status_code == 502
    (key,) = store.keys()
    manifest = store.json(key)
    assert manifest["status"] == "failed"
    assert "start_egress refused" in manifest["error"]
    assert "delete_room" in livekit.names()


async def _create(client, **overrides) -> str:
    payload = {"script_id": "support-handoff", "session_class": "standard", "mode": "scripted"}
    payload.update(overrides)
    response = await client.post("/api/sessions", json=payload)
    assert response.status_code == 201
    return response.json()["session_id"]


@pytest.mark.asyncio
async def test_list_detail_patch_and_delete(client, store, livekit, monkeypatch):
    monkeypatch.setattr(sessions_service, "get_presigned_url", lambda *a, **k: "https://signed")
    sid = await _create(client)

    listing = (await client.get("/api/sessions", params={"session_class": "standard"})).json()
    assert [i["session_id"] for i in listing["items"]] == [sid]
    assert (await client.get("/api/sessions", params={"status": "processed"})).json()["items"] == []

    detail = (await client.get(f"/api/sessions/{sid}")).json()
    assert detail["manifest"]["session_id"] == sid
    assert detail["recording_url"] is None  # still recording

    patched = await client.patch(f"/api/sessions/{sid}", json={"session_class": "hold", "label": "keep"})
    assert patched.status_code == 200
    assert patched.json()["retention"] == {
        "session_class": "hold",
        "retain_days": None,
        "retain_until": None,
        "removed_at": None,
    }
    assert patched.json()["label"] == "keep"

    deleted = await client.delete(f"/api/sessions/{sid}")
    assert deleted.status_code == 204
    assert store.keys() == []
    assert (await client.get(f"/api/sessions/{sid}")).status_code == 404


@pytest.mark.asyncio
async def test_list_paginates_with_cursor(client, store, livekit):
    ids = [await _create(client) for _ in range(3)]
    first = (await client.get("/api/sessions", params={"limit": 2})).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    second = (await client.get("/api/sessions", params={"limit": 2, "cursor": first["next_cursor"]})).json()
    seen = [i["session_id"] for i in first["items"] + second["items"]]
    assert sorted(seen) == sorted(ids)
    assert second["next_cursor"] is None


@pytest.mark.asyncio
async def test_join_token_only_for_live_interactive_sessions(client, store, livekit, lk_keys):
    scripted = await _create(client)
    assert (await client.post(f"/api/sessions/{scripted}/token", json={"identity": "me"})).status_code == 409
    interactive = await _create(client, mode="interactive")
    response = await client.post(f"/api/sessions/{interactive}/token", json={"identity": "me"})
    assert response.status_code == 200
    assert response.json()["room"] == interactive
    assert response.json()["url"] == lk_keys.livekit_public_url


@pytest.mark.asyncio
async def test_unknown_or_malformed_session_is_404(client, store):
    assert (await client.get("/api/sessions/s-20261119-ffffff")).status_code == 404
    assert (await client.get("/api/sessions/..%2Fetc")).status_code == 404


@pytest.mark.asyncio
async def test_reprocess_requires_a_recording(client, store, livekit):
    sid = await _create(client)
    assert (await client.post(f"/api/sessions/{sid}/reprocess")).status_code == 409
