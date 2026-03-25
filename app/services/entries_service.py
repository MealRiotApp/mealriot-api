from datetime import datetime, timezone, date
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.models import FoodEntry, RecentFood, User, WaterLog


async def _update_streak(db: AsyncSession, user: User, today: date) -> None:
    """Increment or reset the user's logging streak."""
    if hasattr(today, "date"):
        today = today.date()
    last = user.last_log_date
    if hasattr(last, "date"):
        last = last.date()
    if last == today:
        return
    if last and (today - last).days == 1:
        user.current_streak += 1
    else:
        user.current_streak = 1
    user.last_log_date = today
    if user.current_streak > user.longest_streak:
        user.longest_streak = user.current_streak


def _sum_items(items: list[dict]) -> tuple[int, float, float, float]:
    calories = sum(int(i.get("calories", 0)) for i in items)
    protein = sum(float(i.get("protein_g", 0)) for i in items)
    fat = sum(float(i.get("fat_g", 0)) for i in items)
    carbs = sum(float(i.get("carbs_g", 0)) for i in items)
    return calories, round(protein, 2), round(fat, 2), round(carbs, 2)


async def _upsert_recent_foods(db: AsyncSession, user_id: UUID, items: list[dict]) -> None:
    for item in items:
        food_name = item.get("food_name", "").lower().strip()
        if not food_name:
            continue
        result = await db.execute(
            select(RecentFood).where(
                RecentFood.user_id == user_id,
                RecentFood.food_name == food_name,
            )
        )
        existing = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if existing:
            existing.use_count += 1
            existing.last_used_at = now
            existing.grams = float(item.get("grams", 0))
            existing.calories = int(item.get("calories", 0))
            existing.protein_g = float(item.get("protein_g", 0))
            existing.fat_g = float(item.get("fat_g", 0))
            existing.carbs_g = float(item.get("carbs_g", 0))
            existing.food_name_he = item.get("food_name_he")
        else:
            db.add(RecentFood(
                user_id=user_id,
                food_name=food_name,
                food_name_he=item.get("food_name_he"),
                grams=float(item.get("grams", 0)),
                calories=int(item.get("calories", 0)),
                protein_g=float(item.get("protein_g", 0)),
                fat_g=float(item.get("fat_g", 0)),
                carbs_g=float(item.get("carbs_g", 0)),
                use_count=1,
                last_used_at=now,
            ))


async def create_entry(db: AsyncSession, user: User, data: dict) -> FoodEntry:
    items = data["items"]
    calories, protein, fat, carbs = _sum_items(items)
    logged_at = data.get("logged_at") or datetime.now(timezone.utc)

    entry = FoodEntry(
        user_id=user.id,
        description=data["description"],
        source=data["source"],
        image_url=data.get("image_url"),
        meal_type=data.get("meal_type", "snack"),
        items=items,
        total_calories=calories,
        total_protein_g=protein,
        total_fat_g=fat,
        total_carbs_g=carbs,
        logged_at=logged_at,
    )
    db.add(entry)
    await db.flush()
    await _upsert_recent_foods(db, user.id, items)
    today = (logged_at if isinstance(logged_at, date) else logged_at.date()) if logged_at else date.today()
    await _update_streak(db, user, today)
    await db.commit()
    await db.refresh(entry)
    return entry


async def list_entries_for_date(db: AsyncSession, user_id: UUID, target_date: date) -> list[FoodEntry]:
    stmt = (
        select(FoodEntry)
        .where(
            FoodEntry.user_id == user_id,
            func.date(FoodEntry.logged_at) == target_date,
        )
        .order_by(FoodEntry.logged_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_entry(db: AsyncSession, user_id: UUID, entry_id: UUID, items: list[dict]) -> FoodEntry:
    from fastapi import HTTPException
    result = await db.execute(
        select(FoodEntry).where(FoodEntry.id == entry_id, FoodEntry.user_id == user_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Entry not found"}},
        )
    calories, protein, fat, carbs = _sum_items(items)
    entry.items = items
    entry.total_calories = calories
    entry.total_protein_g = protein
    entry.total_fat_g = fat
    entry.total_carbs_g = carbs
    await db.commit()
    await db.refresh(entry)
    return entry


async def delete_entry(db: AsyncSession, user_id: UUID, entry_id: UUID) -> None:
    from fastapi import HTTPException
    result = await db.execute(
        select(FoodEntry).where(FoodEntry.id == entry_id, FoodEntry.user_id == user_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Entry not found"}},
        )

    # Subtract water that was added when this entry was created
    if entry.water_ml and entry.water_ml > 0:
        entry_date = entry.logged_at.date() if hasattr(entry.logged_at, 'date') else entry.logged_at
        wl_result = await db.execute(
            select(WaterLog).where(
                WaterLog.user_id == user_id,
                WaterLog.date == entry_date,
            )
        )
        wl = wl_result.scalar_one_or_none()
        if wl:
            wl.amount_ml = max(0, wl.amount_ml - entry.water_ml)

    await db.delete(entry)
    await db.commit()
