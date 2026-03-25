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


def _calc_water_ml(items: list[dict]) -> int:
    """Sum water ml from drink items."""
    total = 0
    for item in items:
        if item.get("is_drink"):
            vol = item.get("volume_ml", item.get("grams", 0))
            pct = item.get("water_pct", 0)
            total += round(vol * pct / 100)
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
    """Create entry/entries. Returns dict with 'entries' list and 'drink_suggestions'."""
    all_items = data["items"]
    logged_at = data.get("logged_at") or datetime.now(timezone.utc)
    # Always extract a pure date object — datetime is a subclass of date,
    # so isinstance(datetime_obj, date) is True, which was causing datetime
    # to be passed to WaterLog queries instead of date, breaking PostgreSQL.
    if logged_at and isinstance(logged_at, datetime):
        today = logged_at.date()
    elif logged_at and isinstance(logged_at, date):
        today = logged_at
    else:
        today = date.today()

    food_items = [i for i in all_items if not i.get("is_drink")]
    drink_items = [i for i in all_items if i.get("is_drink")]

    entries = []

    # Create food entry if there are food items
    if food_items:
        calories, protein, fat, carbs = _sum_items(food_items)
        # Build description from food items only (not the full input which may include drinks)
        food_desc = ", ".join(i.get("food_name", "Food") for i in food_items) if drink_items else data["description"]
        food_entry = FoodEntry(
            user_id=user.id,
            description=food_desc,
            source=data["source"],
            image_url=data.get("image_url"),
            meal_type=data.get("meal_type", "snack"),
            items=food_items,
            total_calories=calories,
            total_protein_g=protein,
            total_fat_g=fat,
            total_carbs_g=carbs,
            water_ml=0,
            logged_at=logged_at,
        )
        db.add(food_entry)
        entries.append(food_entry)
        await _upsert_recent_foods(db, user.id, food_items)

    # Create drink entry if there are drink items
    if drink_items:
        calories, protein, fat, carbs = _sum_items(drink_items)
        water_ml = _calc_water_ml(drink_items)
        drink_desc = ", ".join(i.get("food_name", "Drink") for i in drink_items)
        drink_entry = FoodEntry(
            user_id=user.id,
            description=drink_desc,
            source="drink",
            image_url=data.get("image_url") if not food_items else None,
            meal_type=data.get("meal_type", "snack"),
            items=drink_items,
            total_calories=calories,
            total_protein_g=protein,
            total_fat_g=fat,
            total_carbs_g=carbs,
            water_ml=water_ml,
            logged_at=logged_at,
        )
        db.add(drink_entry)
        entries.append(drink_entry)
        await _upsert_recent_foods(db, user.id, drink_items)

    # Flush entries first to avoid autoflush conflicts during water upsert
    await db.flush()

    # Upsert water after entries are flushed (prevents unique constraint violation)
    if drink_items:
        await _upsert_water(db, user.id, _calc_water_ml(drink_items), today)

    await _update_streak(db, user, today)
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
