from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import require_active_user
from app.core.database import get_db
from app.models.models import User, WeightLog
from app.middleware.rate_limit import limiter

router = APIRouter(prefix="/api/v1/weight", tags=["weight"])


class WeightLogRequest(BaseModel):
    weight_kg: float


class WeightEntry(BaseModel):
    id: str | None = None
    date: str
    weight_kg: float


class WeightHistoryResponse(BaseModel):
    entries: list[WeightEntry]


@router.post("", response_model=WeightEntry)
@limiter.limit("60/minute")
async def log_weight(
    request: Request,
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
    await db.refresh(log)
    return WeightEntry(id=str(log.id), date=today.isoformat(), weight_kg=float(log.weight_kg))


@router.put("/{date_str}", response_model=WeightEntry)
@limiter.limit("60/minute")
async def update_weight(
    request: Request,
    date_str: str,
    body: WeightLogRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    target = date.fromisoformat(date_str)
    result = await db.execute(
        select(WeightLog).where(WeightLog.user_id == current_user.id, WeightLog.date == target)
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(404, detail="Weight entry not found")
    log.weight_kg = body.weight_kg
    await db.commit()
    await db.refresh(log)
    return WeightEntry(id=str(log.id), date=target.isoformat(), weight_kg=float(log.weight_kg))


@router.get("/history", response_model=WeightHistoryResponse)
@limiter.limit("60/minute")
async def get_weight_history(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    since = date.today() - timedelta(days=365)
    result = await db.execute(
        select(WeightLog)
        .where(WeightLog.user_id == current_user.id, WeightLog.date >= since)
        .order_by(WeightLog.date)
    )
    logs = result.scalars().all()
    return WeightHistoryResponse(
        entries=[WeightEntry(id=str(l.id), date=l.date.isoformat(), weight_kg=float(l.weight_kg)) for l in logs]
    )


@router.delete("/{date_str}", status_code=204)
@limiter.limit("60/minute")
async def delete_weight(
    request: Request,
    date_str: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    target = date.fromisoformat(date_str)
    result = await db.execute(
        select(WeightLog).where(WeightLog.user_id == current_user.id, WeightLog.date == target)
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(404, detail="Weight entry not found")
    await db.delete(log)
    await db.commit()
