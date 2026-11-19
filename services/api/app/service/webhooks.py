"""LiveKit webhook handling: verify, dedupe, keep evidence, update the manifest.

LiveKit retries a webhook it could not deliver, so the same event id can
arrive more than once. Duplicates are detected in process and, across restarts,
by the evidence object already being in B2.
"""

import logging
from collections import OrderedDict
from threading import Lock

from app.repo import livekit_api, session_store
from app.service import layout, manifests
from app.types import WebhookAck
from app.types.sessions import WebhookRef
from app.types.webhook import ParsedWebhook

logger = logging.getLogger(__name__)

EGRESS_EVENTS = ("egress_started", "egress_updated", "egress_ended")
ARCHIVED_EVENTS = (*EGRESS_EVENTS, "room_finished")

_SEEN_MAX = 4096
_seen: OrderedDict[str, None] = OrderedDict()
_seen_lock = Lock()

WebhookVerificationError = livekit_api.WebhookVerificationError


def _reset_state() -> None:
    with _seen_lock:
        _seen.clear()


def _remember(event_id: str) -> bool:
    """Record an event id. Returns False when it was already seen."""
    with _seen_lock:
        if event_id in _seen:
            return False
        _seen[event_id] = None
        if len(_seen) > _SEEN_MAX:
            _seen.popitem(last=False)
        return True


def _forget(event_id: str) -> None:
    with _seen_lock:
        _seen.pop(event_id, None)


def _session_for(event: ParsedWebhook) -> str | None:
    room = event.room_name
    if not room or not layout.SESSION_ID_RE.match(room):
        return None
    return room


def _apply(event: ParsedWebhook, session_id: str, evidence_key: str) -> bool:
    """Fold the event into the manifest. Returns True when post-processing should run."""
    with manifests.session_lock(session_id):
        manifest = manifests.load(session_id)
        if manifest is None:
            return False
        egress = event.egress
        if egress is None:
            return False  # room_finished: evidence only
        state = manifest.egress
        state.egress_id = state.egress_id or egress.egress_id
        state.status = egress.status
        state.started_at = state.started_at or manifests.ns_to_datetime(egress.started_at_ns)
        state.ended_at = manifests.ns_to_datetime(egress.ended_at_ns) or state.ended_at
        state.error = egress.error or None
        state.webhook = WebhookRef(
            event_id=event.event_id,
            event=event.event,
            received_at=manifests.utcnow(),
            evidence_key=evidence_key,
        )
        run_postprocess = False
        if event.event == "egress_ended":
            if egress.status == "EGRESS_COMPLETE" and egress.files:
                result = egress.files[0]
                recording = manifest.recording
                recording.location = result.location
                recording.filename = result.filename
                recording.size_bytes = result.size
                recording.duration_s = manifests.ns_to_seconds(result.duration_ns)
                if not result.location.endswith(recording.key):
                    logger.warning(
                        "Egress location %s does not end with %s", result.location, recording.key
                    )
                manifest.status = "recorded"
                manifest.error = None
                manifest.retention = manifests.retention_for(
                    manifest.session_class, manifests.retention_anchor(manifest)
                )
                run_postprocess = True
            else:
                manifest.status = "failed"
                manifest.error = egress.error or f"Egress ended with {egress.status}"
        manifests.save(manifest)
        return run_postprocess


def receive(body: str, authorization: str) -> tuple[WebhookAck, str | None]:
    """Handle one webhook. Returns the ack and a session id to post-process, if any.

    Raises WebhookVerificationError for an unsigned or tampered body.
    """
    event = livekit_api.verify_webhook(body, authorization)
    session_id = _session_for(event)
    if event.event not in ARCHIVED_EVENTS or session_id is None:
        return WebhookAck(received=True, event=event.event), None

    evidence_key = layout.webhook_key(session_id, event.event_id)
    if not _remember(event.event_id) or session_store.head(evidence_key) is not None:
        logger.info("Duplicate webhook %s (%s) ignored", event.event_id, event.event)
        return WebhookAck(received=True, event=event.event, duplicate=True), None

    if manifests.load(session_id) is None:
        return WebhookAck(received=True, event=event.event), None

    try:
        session_store.put_bytes(evidence_key, body.encode("utf-8"), "application/json")
        run_postprocess = _apply(event, session_id, evidence_key)
    except Exception:
        _forget(event.event_id)  # let LiveKit's retry be processed, not deduped
        raise
    logger.info("Webhook %s for %s stored at %s", event.event, session_id, evidence_key)
    return WebhookAck(received=True, event=event.event), session_id if run_postprocess else None
