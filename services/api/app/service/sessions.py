"""Session lifecycle: create, list, read, edit, delete, reprocess, join.

Create order: room -> manifest (status `recording`) -> agent dispatch -> Egress.
The manifest is written before anything records, so a session that fails later
still has one, marked `failed` with the reason.
"""

import logging
from concurrent.futures import ThreadPoolExecutor

from app.config import settings
from app.repo import get_presigned_url, livekit_api, session_store
from app.service import layout, manifests
from app.service.scripts import get_script, list_scripts
from app.types import (
    JoinToken,
    ScriptList,
    SessionCreate,
    SessionDetail,
    SessionList,
    SessionManifest,
    SessionUpdate,
)
from app.types.sessions import Evaluation, Transcript, WebhookEvidence

logger = logging.getLogger(__name__)

MAX_LIMIT = 200


class SessionNotFound(LookupError):
    pass


class SessionConflict(Exception):
    """The request is valid but not for this session's current state."""


class LiveKitUnavailable(RuntimeError):
    pass


def require_valid_id(session_id: str) -> None:
    try:
        layout.session_date(session_id)
    except layout.InvalidSessionId:
        raise SessionNotFound(session_id) from None


def get_manifest(session_id: str) -> SessionManifest:
    require_valid_id(session_id)
    manifest = manifests.load(session_id)
    if manifest is None:
        raise SessionNotFound(session_id)
    return manifest


def scripts() -> ScriptList:
    return ScriptList(items=[s.info() for s in list_scripts()])


def create_session(request: SessionCreate) -> SessionManifest:
    get_script(request.script_id)  # ScriptNotFound -> 400 before anything exists
    now = manifests.utcnow()
    session_id = layout.new_session_id(now)
    agent_metadata = {
        "session_id": session_id,
        "script_id": request.script_id,
        "mode": request.mode,
    }
    try:
        livekit_api.create_room(session_id, agent_metadata)
    except livekit_api.LiveKitError as e:
        raise LiveKitUnavailable(str(e)) from e

    manifest = manifests.new_manifest(session_id, request, now)
    manifests.save(manifest)
    logger.info("Session created: %s class=%s mode=%s", session_id, request.session_class, request.mode)

    try:
        livekit_api.dispatch_agent(session_id, agent_metadata)
        egress_id, egress_status = livekit_api.start_egress(
            session_id, layout.recording_key(session_id)
        )
    except livekit_api.LiveKitError as e:
        with manifests.session_lock(session_id):
            failed = manifests.load(session_id) or manifest
            failed.status = "failed"
            failed.error = f"LiveKit start failed: {e}"
            manifests.save(failed)
        try:
            livekit_api.delete_room(session_id)
        except livekit_api.LiveKitError:
            logger.warning("Could not delete room %s after a failed start", session_id)
        raise LiveKitUnavailable(str(e)) from e

    # A webhook may already have updated the manifest; merge, never overwrite.
    with manifests.session_lock(session_id):
        current = manifests.load(session_id) or manifest
        current.egress.egress_id = current.egress.egress_id or egress_id
        current.egress.status = current.egress.status or egress_status
        manifests.save(current)
    return current


def _load_many(keys: list[str]) -> list[SessionManifest]:
    def load(key: str) -> SessionManifest | None:
        data = session_store.get_json(key)
        return SessionManifest.model_validate(data) if data else None

    if not keys:
        return []
    with ThreadPoolExecutor(max_workers=8) as pool:
        return [m for m in pool.map(load, keys) if m is not None]


def all_manifests() -> list[SessionManifest]:
    return _load_many(manifests.list_manifest_keys())


def list_sessions(
    date: str | None = None,
    session_class: str | None = None,
    status: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> SessionList:
    if limit < 1 or limit > MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
    keys = manifests.list_manifest_keys()
    if date:
        keys = [k for k in keys if f"sessions/{date}/" in k]
    if cursor:
        keys = [k for k in keys if (layout.session_id_from_key(k) or "") < cursor]

    items = []
    consumed = 0
    while consumed < len(keys) and len(items) < limit:
        batch = keys[consumed : consumed + limit]
        consumed += len(batch)
        for manifest in _load_many(batch):
            if session_class and manifest.session_class != session_class:
                continue
            if status and manifest.status != status:
                continue
            items.append(manifests.summary(manifest))
    truncated = len(items) > limit
    items = items[:limit]
    more = truncated or consumed < len(keys)
    next_cursor = items[-1].session_id if items and more else None
    return SessionList(items=items, next_cursor=next_cursor)


def get_detail(session_id: str) -> SessionDetail:
    manifest = get_manifest(session_id)
    recording_url = None
    if manifest.status in ("recorded", "processed", "failed") and session_store.head(
        manifest.recording.key
    ):
        recording_url = get_presigned_url(
            manifest.recording.key,
            filename=f"{session_id}.ogg",
            expires_in=900,
            disposition="inline",
        )
    transcript = session_store.get_json(layout.transcript_key(session_id))
    evaluation = session_store.get_json(layout.evaluation_key(session_id))
    evidence = []
    for obj in session_store.list_objects(layout.webhooks_prefix(session_id)):
        body = session_store.get_json(obj["Key"]) or {}
        evidence.append(
            WebhookEvidence(
                key=obj["Key"], event=str(body.get("event", "")), event_id=str(body.get("id", ""))
            )
        )
    return SessionDetail(
        manifest=manifest,
        recording_url=recording_url,
        transcript=Transcript.model_validate(transcript) if transcript else None,
        evaluation=Evaluation.model_validate(evaluation) if evaluation else None,
        webhooks=evidence,
    )


def update_session(session_id: str, request: SessionUpdate) -> SessionManifest:
    get_manifest(session_id)
    with manifests.session_lock(session_id):
        manifest = get_manifest(session_id)
        if request.label is not None:
            manifest.label = request.label
        if request.session_class is not None:
            if manifest.status == "expired":
                raise SessionConflict("An expired session's recording is gone; its class is final.")
            manifest.session_class = request.session_class
            manifest.retention = manifests.retention_for(
                request.session_class, manifests.retention_anchor(manifest)
            )
        manifests.save(manifest)
    return manifest


def delete_session(session_id: str) -> None:
    manifest = get_manifest(session_id)
    if manifest.status == "recording":
        try:
            livekit_api.delete_room(session_id)
        except livekit_api.LiveKitError:
            logger.warning("Room %s was already gone while deleting", session_id)
    removed, freed = session_store.delete_all_versions(layout.session_prefix(session_id))
    logger.info("Session deleted: %s versions=%d bytes=%d", session_id, removed, freed)


def prepare_reprocess(session_id: str) -> SessionManifest:
    manifest = get_manifest(session_id)
    if manifest.status in ("recording", "expired"):
        raise SessionConflict(f"Cannot reprocess a session that is {manifest.status}.")
    if session_store.head(manifest.recording.key) is None:
        raise SessionConflict("The recording is not in B2 yet.")
    return manifest


def join_token(session_id: str, identity: str) -> JoinToken:
    manifest = get_manifest(session_id)
    if manifest.mode != "interactive":
        raise SessionConflict("Only interactive sessions accept a browser participant.")
    if manifest.status != "recording":
        raise SessionConflict("The room has closed; this session is no longer live.")
    token = livekit_api.create_join_token(session_id, identity)
    return JoinToken(url=settings.livekit_public_url, token=token, room=session_id)
