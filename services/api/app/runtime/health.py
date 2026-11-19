from fastapi import APIRouter

from app.repo import check_connectivity
from app.repo.livekit_api import check_livekit
from app.types import HealthStatus

router = APIRouter()


# Sync `def` so the blocking checks run in Starlette's threadpool rather than
# on the event loop (see runtime/files.py rationale).
@router.get("/health", response_model=HealthStatus)
def health():
    b2_ok = check_connectivity()
    return HealthStatus(
        status="healthy" if b2_ok else "degraded",
        b2_connected=b2_ok,
        livekit_connected=check_livekit(),
    )
