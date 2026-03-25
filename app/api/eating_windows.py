from datetime import time
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.api.deps import require_active_user
from app.core.database import get_db
from app.models.models import User, EatingWindow
from app.schemas.eating_windows import (
    EatingWindowsResponse, EatingWindowItem, UpdateEatingWindowsRequest,
)
from app.middleware.rate_limit import limiter

router = APIRouter(prefix="/api/v1/eating-windows", tags=["eating-windows"])


@router.get("", response_model=EatingWindowsResponse)
@limiter.limit("60/minute")
async def get_eating_windows(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    result = await db.execute(
        select(EatingWindow).where(EatingWindow.user_id == current_user.id)
    )
    windows = result.scalars().all()
    if not windows:
        return EatingWindowsResponse(windows=[
            EatingWindowItem(meal_type="breakfast", start_time="07:00", end_time="09:00"),
            EatingWindowItem(meal_type="lunch", start_time="12:00", end_time="14:00"),
            EatingWindowItem(meal_type="dinner", start_time="18:00", end_time="20:00"),
        ])
    return EatingWindowsResponse(
        windows=[
            EatingWindowItem(
                meal_type=w.meal_type,
                start_time=w.start_time.strftime("%H:%M"),
                end_time=w.end_time.strftime("%H:%M"),
            )
            for w in windows
        ]
    )


@router.put("", response_model=EatingWindowsResponse)
@limiter.limit("60/minute")
async def update_eating_windows(
    request: Request,
    body: UpdateEatingWindowsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    await db.execute(
        delete(EatingWindow).where(EatingWindow.user_id == current_user.id)
    )
    for w in body.windows:
        h_s, m_s = map(int, w.start_time.split(":"))
        h_e, m_e = map(int, w.end_time.split(":"))
        db.add(EatingWindow(
            user_id=current_user.id,
            meal_type=w.meal_type,
            start_time=time(h_s, m_s),
            end_time=time(h_e, m_e),
        ))
    await db.commit()
    return await get_eating_windows(request=request, db=db, current_user=current_user)
