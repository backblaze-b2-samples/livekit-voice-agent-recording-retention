import re

from fastapi import APIRouter, HTTPException

from app.service import retention as service
from app.types import (
    RetentionPolicy,
    RetentionReport,
    RetentionReportList,
    RetentionRunRequest,
)

router = APIRouter()

_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@router.get("/retention/policy", response_model=RetentionPolicy)
def policy_endpoint():
    return service.policy()


@router.post("/retention/runs", response_model=RetentionReport)
def run_endpoint(request: RetentionRunRequest):
    return service.run(as_of=request.as_of, dry_run=request.dry_run)


@router.get("/retention/reports", response_model=RetentionReportList)
def list_reports_endpoint():
    return service.list_reports()


@router.get("/retention/reports/{day}", response_model=RetentionReport)
def get_report_endpoint(day: str):
    if not _DAY.match(day):
        raise HTTPException(status_code=400, detail="Report date must be YYYY-MM-DD")
    report = service.get_report(day)
    if report is None:
        raise HTTPException(status_code=404, detail=f"No retention report for {day}")
    return report
