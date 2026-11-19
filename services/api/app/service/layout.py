"""B2 key layout for the archive. Pure functions, no I/O.

    <ARCHIVE_PREFIX>sessions/<YYYY-MM-DD>/<room>/recording.ogg
    <ARCHIVE_PREFIX>sessions/<YYYY-MM-DD>/<room>/manifest.json
    <ARCHIVE_PREFIX>sessions/<YYYY-MM-DD>/<room>/transcript.json
    <ARCHIVE_PREFIX>sessions/<YYYY-MM-DD>/<room>/evaluation.json
    <ARCHIVE_PREFIX>sessions/<YYYY-MM-DD>/<room>/webhooks/<event_id>.json
    <ARCHIVE_PREFIX>reports/<YYYY-MM-DD>.json

The session id is the room name, `s-<YYYYMMDD>-<6 hex>`, and the date segment
is derived from it, so every key is known before Egress starts.
"""

import re
import secrets
from datetime import datetime

from app.config import settings

SESSION_ID_RE = re.compile(r"^s-(\d{4})(\d{2})(\d{2})-([0-9a-f]{6})$")
_EVENT_ID_RE = re.compile(r"[^A-Za-z0-9_.-]")

RECORDING = "recording.ogg"
MANIFEST = "manifest.json"
TRANSCRIPT = "transcript.json"
EVALUATION = "evaluation.json"


class InvalidSessionId(ValueError):
    """The value is not a session id this app minted."""


def new_session_id(now: datetime) -> str:
    return f"s-{now:%Y%m%d}-{secrets.token_hex(3)}"


def session_date(session_id: str) -> str:
    match = SESSION_ID_RE.match(session_id)
    if not match:
        raise InvalidSessionId(session_id)
    year, month, day, _ = match.groups()
    return f"{year}-{month}-{day}"


def sessions_root() -> str:
    return f"{settings.archive_prefix}sessions/"


def session_prefix(session_id: str) -> str:
    return f"{sessions_root()}{session_date(session_id)}/{session_id}/"


def manifest_key(session_id: str) -> str:
    return session_prefix(session_id) + MANIFEST


def recording_key(session_id: str) -> str:
    return session_prefix(session_id) + RECORDING


def transcript_key(session_id: str) -> str:
    return session_prefix(session_id) + TRANSCRIPT


def evaluation_key(session_id: str) -> str:
    return session_prefix(session_id) + EVALUATION


def webhooks_prefix(session_id: str) -> str:
    return session_prefix(session_id) + "webhooks/"


def webhook_key(session_id: str, event_id: str) -> str:
    safe = _EVENT_ID_RE.sub("_", event_id) or "unknown"
    return f"{webhooks_prefix(session_id)}{safe}.json"


def session_id_from_key(key: str) -> str | None:
    """`.../sessions/<date>/<sid>/manifest.json` -> `<sid>`; None for other keys."""
    parts = key.split("/")
    if len(parts) < 2 or parts[-1] != MANIFEST:
        return None
    candidate = parts[-2]
    return candidate if SESSION_ID_RE.match(candidate) else None


def reports_root() -> str:
    return f"{settings.archive_prefix}reports/"


def report_key(day: str) -> str:
    return f"{reports_root()}{day}.json"
