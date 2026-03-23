from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import require_active_user
from app.core.database import get_db
from app.models.models import User, DailyPoints
from app.schemas.social import TodayPointsResponse, WeekPointsResponse

router = APIRouter(prefix="/api/v1/points", tags=["points"])


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


@router.get("/today", response_model=TodayPointsResponse)
async def get_today_points(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    today = date.today()
    result = await db.execute(
        select(DailyPoints).where(
            DailyPoints.user_id == current_user.id,
            DailyPoints.date == today,
        )
    )
    dp = result.scalar_one_or_none()
    if not dp:
        return TodayPointsResponse(
            date=today.isoformat(),
            calorie_points=0, logging_points=0, macro_points=0, total_points=0,
        )
    return TodayPointsResponse(
        date=dp.date.isoformat(),
        calorie_points=dp.calorie_points,
        logging_points=dp.logging_points,
        macro_points=dp.macro_points,
        total_points=dp.total_points,
    )


@router.get("/week", response_model=WeekPointsResponse)
async def get_week_points(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    today = date.today()
    ws = _week_start(today)
    result = await db.execute(
        select(DailyPoints)
        .where(
            DailyPoints.user_id == current_user.id,
            DailyPoints.date >= ws,
            DailyPoints.date <= today,
        )
        .order_by(DailyPoints.date)
    )
    rows = result.scalars().all()
    total = sum(r.total_points for r in rows)
    days = [{"date": r.date.isoformat(), "total_points": r.total_points} for r in rows]
    return WeekPointsResponse(week_start=ws.isoformat(), total_points=total, days=days)
