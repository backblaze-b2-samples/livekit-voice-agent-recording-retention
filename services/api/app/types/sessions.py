"""Session archive models: the per-session manifest and the API shapes around it.

The manifest is the primary entity. It is written to B2 before Egress starts and
updated by the webhook receiver and post-processing, so every session has one
from the moment it exists.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.types.base import ResponseModel

SessionClass = Literal["debug", "standard", "training", "hold"]
SessionMode = Literal["scripted", "interactive"]
SessionStatus = Literal["recording", "recorded", "processed", "failed", "expired"]

SESSION_CLASSES: tuple[str, ...] = ("debug", "standard", "training", "hold")
SESSION_STATUSES: tuple[str, ...] = ("recording", "recorded", "processed", "failed", "expired")


class WebhookRef(ResponseModel):
    """The verified webhook that last changed this session's Egress state."""

    event_id: str
    event: str
    received_at: datetime
    evidence_key: str = Field(description="B2 key of the raw, verified webhook body.")


class EgressState(ResponseModel):
    egress_id: str | None = None
    status: str | None = Field(default=None, description="LiveKit EgressStatus name.")
    started_at: datetime | None = None
    ended_at: datetime | None = None
    error: str | None = None
    webhook: WebhookRef | None = None


class RecordingInfo(ResponseModel):
    key: str = Field(description="Deterministic key Egress was told to write.")
    location: str | None = Field(default=None, description="file_results[0].location from Egress.")
    filename: str | None = None
    size_bytes: int | None = None
    duration_s: float | None = None
    sha256: str | None = None
    etag: str | None = None
    content_type: str = "audio/ogg"


class TranscriptionInfo(ResponseModel):
    key: str
    model: str
    device: str
    language: str | None = None
    word_count: int = 0


class EvaluationInfo(ResponseModel):
    key: str
    wer: float
    expected_phrases_found: int
    expected_phrases_total: int
    passed: bool


class RetentionInfo(ResponseModel):
    session_class: SessionClass
    retain_days: int | None = Field(description="Null means keep indefinitely (hold).")
    retain_until: datetime | None = None
    removed_at: datetime | None = None


class SessionManifest(ResponseModel):
    """`sessions/<date>/<room>/manifest.json` in B2."""

    schema_version: int = 1
    session_id: str
    date: str
    session_class: SessionClass
    script_id: str
    mode: SessionMode
    label: str = ""
    status: SessionStatus
    created_at: datetime
    error: str | None = None
    egress: EgressState = Field(default_factory=EgressState)
    recording: RecordingInfo
    transcription: TranscriptionInfo | None = None
    evaluation: EvaluationInfo | None = None
    retention: RetentionInfo


class SessionCreate(BaseModel):
    script_id: str = Field(min_length=1, max_length=64)
    session_class: SessionClass = "debug"
    mode: SessionMode = "scripted"
    label: str = Field(default="", max_length=120)


class SessionUpdate(BaseModel):
    session_class: SessionClass | None = None
    label: str | None = Field(default=None, max_length=120)


class SessionSummary(ResponseModel):
    session_id: str
    date: str
    session_class: SessionClass
    script_id: str
    mode: SessionMode
    label: str
    status: SessionStatus
    created_at: datetime
    duration_s: float | None = None
    size_bytes: int | None = None
    wer: float | None = None
    passed: bool | None = None
    retain_until: datetime | None = None


class SessionList(ResponseModel):
    items: list[SessionSummary]
    next_cursor: str | None = None


class TranscriptSegment(ResponseModel):
    start: float
    end: float
    text: str


class Transcript(ResponseModel):
    """`transcript.json`: what faster-whisper heard in the recording."""

    session_id: str
    model: str
    device: str
    language: str | None = None
    text: str
    segments: list[TranscriptSegment]


class Evaluation(ResponseModel):
    """`evaluation.json`: deterministic score of the transcript against the script."""

    session_id: str
    script_id: str
    reference_text: str
    hypothesis_text: str
    wer: float
    max_wer: float
    expected_phrases: list[str]
    phrases_found: list[str]
    phrases_missing: list[str]
    passed: bool


class WebhookEvidence(ResponseModel):
    key: str
    event: str
    event_id: str


class SessionDetail(ResponseModel):
    manifest: SessionManifest
    recording_url: str | None = Field(
        default=None, description="Presigned GET for playback, when the recording exists."
    )
    transcript: Transcript | None = None
    evaluation: Evaluation | None = None
    webhooks: list[WebhookEvidence] = Field(default_factory=list)


class ScriptInfo(ResponseModel):
    id: str
    title: str
    description: str
    line_count: int
    expected_duration_s: float


class ScriptList(ResponseModel):
    items: list[ScriptInfo]


class JoinTokenRequest(BaseModel):
    identity: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")


class JoinToken(ResponseModel):
    url: str
    token: str
    room: str


class WebhookAck(ResponseModel):
    received: bool
    event: str
    duplicate: bool = False
