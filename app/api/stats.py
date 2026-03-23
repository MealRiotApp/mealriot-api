from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import require_active_user
from app.core.database import get_db
from app.models.models import User
from app.schemas.stats import DailyStatsResponse, RangeStatsResponse
from app.services.stats_service import get_daily_stats, get_range_stats

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


@router.get("/daily", response_model=DailyStatsResponse)
async def daily_stats(
    date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    return await get_daily_stats(db, current_user, date)


@router.get("/range", response_model=RangeStatsResponse)
async def range_stats(
    start: date = Query(...),
    end: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    return await get_range_stats(db, current_user, start, end)
