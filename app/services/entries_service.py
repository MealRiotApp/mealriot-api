from datetime import datetime, timezone, date
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.models import FoodEntry, RecentFood, User, WaterLog
from app.services.points_service import recalculate_daily_points


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
    calories = sum(int(i.get("calories", 0)) * i.get("quantity", 1) for i in items)
    protein = sum(float(i.get("protein_g", 0)) * i.get("quantity", 1) for i in items)
    fat = sum(float(i.get("fat_g", 0)) * i.get("quantity", 1) for i in items)
    carbs = sum(float(i.get("carbs_g", 0)) * i.get("quantity", 1) for i in items)
    return calories, round(protein, 2), round(fat, 2), round(carbs, 2)


def _item_description(item: dict) -> str:
    """Build description for a single item, with quantity suffix if > 1."""
    name = item.get("food_name", "Food")
    qty = item.get("quantity", 1)
    return f"{name} x{qty}" if qty > 1 else name


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


def _calc_water_ml(items: list[dict]) -> int:
    """Sum water ml from drink items, accounting for quantity."""
    total = 0
    for item in items:
        if item.get("is_drink"):
            vol = item.get("volume_ml", item.get("grams", 0))
            pct = item.get("water_pct", 0)
            qty = item.get("quantity", 1)
            total += round(vol * pct / 100) * qty
    return total


async def _upsert_water(db: AsyncSession, user_id: UUID, water_ml: int, log_date: date) -> None:
    """Add water_ml to the WaterLog for the given date."""
    if water_ml <= 0:
        return
    wl_result = await db.execute(
        select(WaterLog).where(WaterLog.user_id == user_id, WaterLog.date == log_date)
    )
    wl = wl_result.scalar_one_or_none()
    if wl:
        wl.amount_ml = wl.amount_ml + water_ml
    else:
        db.add(WaterLog(user_id=user_id, date=log_date, amount_ml=water_ml))


def _build_drink_suggestions(drink_items: list[dict]) -> list[dict]:
    """Build drink suggestion dicts from drink items."""
    suggestions = []
    for item in drink_items:
        suggestions.append({
            "name": item.get("food_name", "Drink"),
            "name_he": item.get("food_name_he"),
            "icon": "🥤",
            "volume_ml": item.get("volume_ml", item.get("grams", 250)),
            "calories": item.get("calories", 0),
            "sugar_g": 0,
            "protein_g": item.get("protein_g", 0),
            "fat_g": item.get("fat_g", 0),
            "carbs_g": item.get("carbs_g", 0),
            "water_pct": item.get("water_pct", 100),
        })
    return suggestions


async def create_entry(db: AsyncSession, user: User, data: dict) -> dict:
    """Create one entry per item. Returns dict with 'entries' list and 'drink_suggestions'."""
    all_items = data["items"]
    logged_at = data.get("logged_at") or datetime.now(timezone.utc)
    if logged_at and isinstance(logged_at, datetime):
        today = logged_at.date()
    elif logged_at and isinstance(logged_at, date):
        today = logged_at
    else:
        today = date.today()

    food_items = [i for i in all_items if not i.get("is_drink")]
    drink_items = [i for i in all_items if i.get("is_drink")]

    entries = []

    # Create one entry per food item
    for item in food_items:
        calories, protein, fat, carbs = _sum_items([item])
        entry = FoodEntry(
            user_id=user.id,
            description=_item_description(item),
            source=data["source"],
            image_url=data.get("image_url") if len(food_items) == 1 and not drink_items else None,
            meal_type=data.get("meal_type", "snack"),
            items=[item],
            total_calories=calories,
            total_protein_g=protein,
            total_fat_g=fat,
            total_carbs_g=carbs,
            water_ml=0,
            logged_at=logged_at,
        )
        db.add(entry)
        entries.append(entry)

    # Create one entry per drink item
    for item in drink_items:
        calories, protein, fat, carbs = _sum_items([item])
        water_ml = _calc_water_ml([item])
        entry = FoodEntry(
            user_id=user.id,
            description=_item_description(item),
            source="drink",
            image_url=data.get("image_url") if len(drink_items) == 1 and not food_items else None,
            meal_type=data.get("meal_type", "snack"),
            items=[item],
            total_calories=calories,
            total_protein_g=protein,
            total_fat_g=fat,
            total_carbs_g=carbs,
            water_ml=water_ml,
            logged_at=logged_at,
        )
        db.add(entry)
        entries.append(entry)

    await db.flush()

    total_water = _calc_water_ml(drink_items)
    if total_water > 0:
        await _upsert_water(db, user.id, total_water, today)

    await _upsert_recent_foods(db, user.id, all_items)
    await _update_streak(db, user, today)
    await recalculate_daily_points(db, user, target_date=today)
    await db.commit()
    for e in entries:
        await db.refresh(e)

    return {
        "entries": entries,
        "drink_suggestions": _build_drink_suggestions(drink_items),
    }


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
    old_water_ml = entry.water_ml or 0
    calories, protein, fat, carbs = _sum_items(items)
    new_water_ml = _calc_water_ml(items)
    entry.items = items
    entry.total_calories = calories
    entry.total_protein_g = protein
    entry.total_fat_g = fat
    entry.total_carbs_g = carbs
    entry.water_ml = new_water_ml

    # Regenerate description from current items
    if len(items) == 1:
        entry.description = _item_description(items[0])
    else:
        # Legacy multi-item entries: join all item names
        entry.description = ", ".join(_item_description(i) for i in items)

    # Update WaterLog if water amount changed
    water_diff = new_water_ml - old_water_ml
    if water_diff != 0:
        entry_date = entry.logged_at.date() if isinstance(entry.logged_at, datetime) else entry.logged_at
        wl_result = await db.execute(
            select(WaterLog).where(WaterLog.user_id == user_id, WaterLog.date == entry_date)
        )
        wl = wl_result.scalar_one_or_none()
        if wl:
            wl.amount_ml = max(0, wl.amount_ml + water_diff)
        elif water_diff > 0:
            db.add(WaterLog(user_id=user_id, date=entry_date, amount_ml=water_diff))

    entry_date = entry.logged_at.date() if isinstance(entry.logged_at, datetime) else entry.logged_at
    user = await db.get(User, user_id)
    await recalculate_daily_points(db, user, target_date=entry_date)
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

    entry_date = entry.logged_at.date() if hasattr(entry.logged_at, 'date') and callable(entry.logged_at.date) else entry.logged_at
    user = await db.get(User, user_id)
    await db.delete(entry)
    await db.flush()
    await recalculate_daily_points(db, user, target_date=entry_date)
    await db.commit()


async def list_entries_paginated(
    db: AsyncSession, user_id: UUID, limit: int = 20,
    cursor_time: str | None = None, cursor_id: str | None = None,
) -> dict:
    """Return entries newest-first with compound cursor pagination (logged_at + id)."""
    from sqlalchemy import or_, and_
    stmt = (
        select(FoodEntry)
        .where(FoodEntry.user_id == user_id)
        .order_by(FoodEntry.logged_at.desc(), FoodEntry.id.desc())
        .limit(limit + 1)
    )
    if cursor_time and cursor_id:
        from datetime import datetime as dt
        import uuid as uuid_mod
        cursor_dt = dt.fromisoformat(cursor_time)
        cid = uuid_mod.UUID(cursor_id)
        stmt = stmt.where(
            or_(
                FoodEntry.logged_at < cursor_dt,
                and_(FoodEntry.logged_at == cursor_dt, FoodEntry.id < cid),
            )
        )

    result = await db.execute(stmt)
    entries = list(result.scalars().all())

    has_more = len(entries) > limit
    if has_more:
        entries = entries[:limit]

    next_cursor_time = None
    next_cursor_id = None
    if has_more and entries:
        last = entries[-1]
        next_cursor_time = last.logged_at.isoformat()
        next_cursor_id = str(last.id)

    return {
        "entries": entries,
        "next_cursor_time": next_cursor_time,
        "next_cursor_id": next_cursor_id,
        "has_more": has_more,
    }
