from app.types.base import ResponseModel
from app.types.retention import RetentionReportSummary
from app.types.sessions import SessionSummary


class CountBucket(ResponseModel):
    name: str
    count: int


class ArchiveStats(ResponseModel):
    """Dashboard figures, computed from the session manifests in B2."""

    total_sessions: int
    by_class: list[CountBucket]
    by_status: list[CountBucket]
    recorded_seconds: float
    recorded_bytes: int
    recorded_bytes_human: str
    passed_evaluations: int
    last_report: RetentionReportSummary | None = None
    recent_sessions: list[SessionSummary]
