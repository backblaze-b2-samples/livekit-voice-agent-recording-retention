"""Parsed LiveKit webhook, as the repo layer hands it to services.

Plain data so nothing above `repo/` imports the LiveKit SDK.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EgressFile:
    filename: str
    location: str
    size: int
    duration_ns: int


@dataclass(frozen=True)
class EgressSnapshot:
    egress_id: str
    status: str
    room_name: str
    started_at_ns: int
    ended_at_ns: int
    error: str
    files: list[EgressFile] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedWebhook:
    event: str
    event_id: str
    created_at: int
    room_name: str
    egress: EgressSnapshot | None
