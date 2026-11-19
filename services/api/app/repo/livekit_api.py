"""Every LiveKit server call this app makes: rooms, dispatch, Egress, tokens, webhooks.

The LiveKit SDK (`livekit-api`) is confined to this module, like boto3 is to the
rest of `repo/` (asserted by tests/test_structure.py). Services receive plain
data (`app.types.webhook`) and never import the SDK.

The SDK's server client is async (aiohttp). The API's B2 handlers are sync and
run in Starlette's threadpool, so each public function here runs its own short
event loop with `asyncio.run`, which is safe in a worker thread that has no loop.
"""

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from datetime import timedelta
from threading import Lock
from typing import Any

import aiohttp
from livekit import api as lk

from app.config import settings
from app.types.webhook import EgressFile, EgressSnapshot, ParsedWebhook

ATTRIBUTION = "b2ai-livekit-agent-session-archive"


class LiveKitError(RuntimeError):
    """A LiveKit server call failed."""


class WebhookVerificationError(Exception):
    """The webhook body or its signed Authorization token did not verify."""


def _http_url() -> str:
    url = settings.livekit_url
    if url.startswith("ws://"):
        return "http://" + url[len("ws://") :]
    if url.startswith("wss://"):
        return "https://" + url[len("wss://") :]
    return url


def _run[T](call: Callable[[lk.LiveKitAPI], Awaitable[T]], timeout_s: float = 10.0) -> T:
    async def runner() -> T:
        async with lk.LiveKitAPI(
            _http_url(),
            settings.livekit_api_key,
            settings.livekit_api_secret,
            timeout=aiohttp.ClientTimeout(total=timeout_s),
        ) as client:
            return await call(client)

    try:
        return asyncio.run(runner())
    except Exception as e:  # SDK raises TwirpError, aiohttp and OS errors
        raise LiveKitError(f"LiveKit call failed: {e}") from e


# --- Egress request construction (pure, unit-tested) ----------------------


def build_s3_upload(session_id: str) -> lk.S3Upload:
    """The S3 destination Egress's own uploader writes the recording to.

    Endpoint and region both come from `B2_REGION` via `settings.endpoint_url`.
    The proto has no user-agent or custom-header field, so the attribution
    token travels as object metadata (`x-amz-meta-source`) instead.
    """
    return lk.S3Upload(
        access_key=settings.b2_application_key_id,
        secret=settings.b2_application_key,
        region=settings.b2_region,
        endpoint=settings.endpoint_url,
        bucket=settings.b2_bucket_name,
        force_path_style=True,
        metadata={"source": ATTRIBUTION, "session-id": session_id},
    )


def build_egress_request(room_name: str, filepath: str) -> lk.RoomCompositeEgressRequest:
    """Audio-only room composite to one OGG file at a literal (template-free) key."""
    return lk.RoomCompositeEgressRequest(
        room_name=room_name,
        audio_only=True,
        file_outputs=[
            lk.EncodedFileOutput(
                file_type=lk.EncodedFileType.OGG,
                filepath=filepath,
                disable_manifest=True,
                s3=build_s3_upload(room_name),
            )
        ],
    )


# --- Server calls ----------------------------------------------------------


def create_room(name: str, metadata: dict[str, Any]) -> None:
    request = lk.CreateRoomRequest(
        name=name,
        empty_timeout=settings.room_empty_timeout,
        departure_timeout=10,
        metadata=json.dumps(metadata),
    )
    _run(lambda c: c.room.create_room(request))


def dispatch_agent(room_name: str, metadata: dict[str, Any]) -> str:
    request = lk.CreateAgentDispatchRequest(
        agent_name=settings.agent_name, room=room_name, metadata=json.dumps(metadata)
    )
    dispatch = _run(lambda c: c.agent_dispatch.create_dispatch(request))
    return dispatch.id


def start_egress(room_name: str, filepath: str) -> tuple[str, str]:
    """Start the recording. Returns (egress_id, status name)."""
    request = build_egress_request(room_name, filepath)
    info = _run(lambda c: c.egress.start_room_composite_egress(request))
    return info.egress_id, lk.EgressStatus.Name(info.status)


def delete_room(name: str) -> None:
    _run(lambda c: c.room.delete_room(lk.DeleteRoomRequest(room=name)))


def create_join_token(room_name: str, identity: str) -> str:
    grants = lk.VideoGrants(
        room_join=True, room=room_name, can_publish=True, can_subscribe=True
    )
    return (
        lk.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(identity)
        .with_grants(grants)
        .with_ttl(timedelta(minutes=30))
        .to_jwt()
    )


_HEALTH_TTL_SECONDS = 5.0
_health_cache: tuple[float, bool] | None = None
_health_lock = Lock()


def check_livekit() -> bool:
    """True when the server answers a room list. Cached briefly, never raises."""
    global _health_cache
    now = time.monotonic()
    with _health_lock:
        if _health_cache is not None and now - _health_cache[0] < _HEALTH_TTL_SECONDS:
            return _health_cache[1]
    if not settings.livekit_api_key or not settings.livekit_api_secret:
        ok = False
    else:
        try:
            _run(lambda c: c.room.list_rooms(lk.ListRoomsRequest()), timeout_s=2.0)
            ok = True
        except LiveKitError:
            ok = False
    with _health_lock:
        _health_cache = (time.monotonic(), ok)
    return ok


# --- Webhooks ----------------------------------------------------------------


def verify_webhook(body: str, authorization: str) -> ParsedWebhook:
    """Verify a LiveKit webhook against the raw body and parse it.

    `body` must be the exact bytes LiveKit sent, decoded as UTF-8: the signed
    token carries a SHA-256 of the body, so re-serialized JSON never verifies.
    """
    if not authorization:
        raise WebhookVerificationError("missing Authorization header")
    receiver = lk.WebhookReceiver(
        lk.TokenVerifier(settings.livekit_api_key, settings.livekit_api_secret)
    )
    try:
        event = receiver.receive(body, authorization)
    except Exception as e:  # the SDK raises bare Exception and jwt errors
        raise WebhookVerificationError(str(e)) from e

    egress = None
    if event.HasField("egress_info"):
        info = event.egress_info
        egress = EgressSnapshot(
            egress_id=info.egress_id,
            status=lk.EgressStatus.Name(info.status),
            room_name=info.room_name,
            started_at_ns=int(info.started_at),
            ended_at_ns=int(info.ended_at),
            error=info.error,
            files=[
                EgressFile(
                    filename=f.filename,
                    location=f.location,
                    size=int(f.size),
                    duration_ns=int(f.duration),
                )
                for f in info.file_results
            ],
        )
    room_name = event.room.name if event.HasField("room") else ""
    return ParsedWebhook(
        event=event.event,
        event_id=event.id,
        created_at=int(event.created_at),
        room_name=room_name or (egress.room_name if egress else ""),
        egress=egress,
    )
