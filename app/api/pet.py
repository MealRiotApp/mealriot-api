from datetime import date, datetime, time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.api.deps import require_active_user
from app.core.database import get_db
from app.models.models import User, CatUnlock, EatingWindow
from app.schemas.pet import (
    PetStatusResponse, CollectionResponse, CatInfo,
    SetActiveCatRequest, SetActiveCatResponse,
    EatingWindowsResponse, EatingWindowItem,
    UpdateEatingWindowsRequest, MessageResponse,
)
from app.services.pet_service import (
    CATS, compute_mood, get_time_of_day_state,
    select_message, get_daily_calorie_pct, get_eating_windows_for_user,
)

router = APIRouter(prefix="/api/v1/pet", tags=["pet"])


@router.get("/status", response_model=PetStatusResponse)
async def get_pet_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    today = date.today()
    cal_pct = await get_daily_calorie_pct(db, current_user, today)
    mood = compute_mood(cal_pct)
    windows = await get_eating_windows_for_user(db, current_user.id)
    now_time = datetime.now().time()
    tod_state = get_time_of_day_state(now_time, windows)
    message, msg_type = select_message(cal_pct, tod_state)

    return PetStatusResponse(
        mood=mood,
        active_cat=current_user.active_cat,
        current_streak=current_user.current_streak,
        longest_streak=current_user.longest_streak,
        message=message,
        message_type=msg_type,
        time_of_day_state=tod_state,
    )


@router.get("/collection", response_model=CollectionResponse)
async def get_collection(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    result = await db.execute(
        select(CatUnlock).where(CatUnlock.user_id == current_user.id)
    )
    unlocks = {u.cat_name: u.unlocked_at for u in result.scalars().all()}

    cats = []
    for cat in CATS:
        unlocked = cat["name"] in unlocks
        unlocked_at = unlocks.get(cat["name"])
        cats.append(CatInfo(
            name=cat["name"],
            emoji=cat["emoji"],
            unlocked=unlocked,
            unlock_streak=cat["unlock_streak"],
            unlocked_at=unlocked_at.isoformat() if unlocked_at else None,
        ))

    return CollectionResponse(cats=cats, active_cat=current_user.active_cat)


@router.post("/active-cat", response_model=SetActiveCatResponse)
async def set_active_cat(
    body: SetActiveCatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    result = await db.execute(
        select(CatUnlock).where(
            CatUnlock.user_id == current_user.id,
            CatUnlock.cat_name == body.cat_name,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "CAT_NOT_UNLOCKED", "message": "You haven't unlocked this cat yet"}},
        )
    current_user.active_cat = body.cat_name
    await db.commit()
    return SetActiveCatResponse(active_cat=body.cat_name)


@router.get("/eating-windows", response_model=EatingWindowsResponse)
async def get_eating_windows(
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


@router.put("/eating-windows", response_model=EatingWindowsResponse)
async def update_eating_windows(
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
    return await get_eating_windows(db=db, current_user=current_user)


@router.post("/message", response_model=MessageResponse)
async def get_message(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    today = date.today()
    cal_pct = await get_daily_calorie_pct(db, current_user, today)
    windows = await get_eating_windows_for_user(db, current_user.id)
    now_time = datetime.now().time()
    tod_state = get_time_of_day_state(now_time, windows)
    message, msg_type = select_message(cal_pct, tod_state)

    return MessageResponse(message=message, message_type=msg_type, cached=False)
