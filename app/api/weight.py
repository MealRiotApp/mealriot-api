from datetime import date, timedelta
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import require_active_user
from app.core.database import get_db
from app.models.models import User, WeightLog

router = APIRouter(prefix="/api/v1/weight", tags=["weight"])


class WeightLogRequest(BaseModel):
    weight_kg: float


class WeightEntry(BaseModel):
    date: str
    weight_kg: float


class WeightHistoryResponse(BaseModel):
    entries: list[WeightEntry]


@router.post("", response_model=WeightEntry)
async def log_weight(
    body: WeightLogRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    today = date.today()
    result = await db.execute(
        select(WeightLog).where(WeightLog.user_id == current_user.id, WeightLog.date == today)
    )
    log = result.scalar_one_or_none()
    if log:
        log.weight_kg = body.weight_kg
    else:
        log = WeightLog(user_id=current_user.id, date=today, weight_kg=body.weight_kg)
        db.add(log)
    await db.commit()
    return WeightEntry(date=today.isoformat(), weight_kg=float(log.weight_kg))


@router.get("/history", response_model=WeightHistoryResponse)
async def get_weight_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    since = date.today() - timedelta(days=90)
    result = await db.execute(
        select(WeightLog)
        .where(WeightLog.user_id == current_user.id, WeightLog.date >= since)
        .order_by(WeightLog.date)
    )
    logs = result.scalars().all()
    return WeightHistoryResponse(
        entries=[WeightEntry(date=l.date.isoformat(), weight_kg=float(l.weight_kg)) for l in logs]
    )
