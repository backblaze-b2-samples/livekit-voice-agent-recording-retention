from fastapi import APIRouter

from app.service.stats import archive_stats
from app.types import ArchiveStats

router = APIRouter()


@router.get("/stats", response_model=ArchiveStats)
def stats_endpoint():
    return archive_stats()
