from datetime import date
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import require_active_user
from app.core.database import get_db
from app.models.models import User, WaterLog

router = APIRouter(prefix="/api/v1/water", tags=["water"])


class WaterAddRequest(BaseModel):
    amount_ml: int


class WaterResponse(BaseModel):
    date: str
    amount_ml: int
    goal_ml: int


@router.get("/today", response_model=WaterResponse)
async def get_today_water(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    today = date.today()
    result = await db.execute(
        select(WaterLog).where(WaterLog.user_id == current_user.id, WaterLog.date == today)
    )
    log = result.scalar_one_or_none()
    return WaterResponse(
        date=today.isoformat(),
        amount_ml=log.amount_ml if log else 0,
        goal_ml=current_user.daily_water_goal_ml,
    )


@router.post("/add", response_model=WaterResponse)
async def add_water(
    body: WaterAddRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    today = date.today()
    result = await db.execute(
        select(WaterLog).where(WaterLog.user_id == current_user.id, WaterLog.date == today)
    )
    log = result.scalar_one_or_none()
    if log:
        log.amount_ml += body.amount_ml
    else:
        log = WaterLog(user_id=current_user.id, date=today, amount_ml=body.amount_ml)
        db.add(log)
    await db.commit()
    await db.refresh(log)
    return WaterResponse(
        date=today.isoformat(),
        amount_ml=log.amount_ml,
        goal_ml=current_user.daily_water_goal_ml,
    )
