"""Retention policy and report models."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.types.base import ResponseModel
from app.types.sessions import SessionClass


class ClassPolicy(ResponseModel):
    session_class: SessionClass
    retain_days: int | None = Field(description="Null means keep indefinitely.")


class RetentionPolicy(ResponseModel):
    classes: list[ClassPolicy]


class RetentionRunRequest(BaseModel):
    as_of: date | None = Field(default=None, description="Defaults to today (UTC).")
    dry_run: bool = True


class RetentionClassResult(ResponseModel):
    session_class: SessionClass
    retain_days: int | None
    kept: list[str]
    removed: list[str]
    already_expired: list[str]


class RetentionReport(ResponseModel):
    """`reports/<as_of>.json`, written by an applied (non dry-run) retention run."""

    schema_version: int = 1
    date: str
    as_of: date
    generated_at: datetime
    dry_run: bool
    report_key: str | None = Field(
        default=None, description="Where the report was written; null for a dry run."
    )
    classes: list[RetentionClassResult]
    kept_total: int
    removed_total: int
    removed_bytes: int


class RetentionReportSummary(ResponseModel):
    date: str
    key: str
    kept_total: int
    removed_total: int
    generated_at: datetime | None = None


class RetentionReportList(ResponseModel):
    items: list[RetentionReportSummary]
