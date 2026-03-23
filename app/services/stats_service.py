from datetime import date, timedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.models import FoodEntry, User


async def get_daily_stats(db: AsyncSession, user: User, target_date: date) -> dict:
    agg_stmt = select(
        func.coalesce(func.sum(FoodEntry.total_calories), 0).label("calories"),
        func.coalesce(func.sum(FoodEntry.total_protein_g), 0).label("protein"),
        func.coalesce(func.sum(FoodEntry.total_fat_g), 0).label("fat"),
        func.coalesce(func.sum(FoodEntry.total_carbs_g), 0).label("carbs"),
    ).where(
        FoodEntry.user_id == user.id,
        func.date(FoodEntry.logged_at) == target_date,
    )
    agg = (await db.execute(agg_stmt)).one()

    entries_stmt = (
        select(FoodEntry)
        .where(
            FoodEntry.user_id == user.id,
            func.date(FoodEntry.logged_at) == target_date,
        )
        .order_by(FoodEntry.logged_at)
    )
    entries = list((await db.execute(entries_stmt)).scalars().all())

    return {
        "date": target_date,
        "total_calories": int(agg.calories),
        "total_protein_g": float(agg.protein),
        "total_fat_g": float(agg.fat),
        "total_carbs_g": float(agg.carbs),
        "goal_calories": user.daily_cal_goal,
        "goal_protein_g": user.daily_protein_goal_g,
        "goal_fat_g": user.daily_fat_goal_g,
        "goal_carbs_g": user.daily_carbs_goal_g,
        "entries": entries,
    }


async def get_range_stats(db: AsyncSession, user: User, start: date, end: date) -> dict:
    stmt = select(
        func.date(FoodEntry.logged_at).label("day"),
        func.coalesce(func.sum(FoodEntry.total_calories), 0).label("calories"),
        func.coalesce(func.sum(FoodEntry.total_protein_g), 0).label("protein"),
        func.coalesce(func.sum(FoodEntry.total_fat_g), 0).label("fat"),
        func.coalesce(func.sum(FoodEntry.total_carbs_g), 0).label("carbs"),
        func.count(FoodEntry.id).label("entry_count"),
    ).where(
        FoodEntry.user_id == user.id,
        func.date(FoodEntry.logged_at) >= start,
        func.date(FoodEntry.logged_at) <= end,
    ).group_by(func.date(FoodEntry.logged_at))
    rows = (await db.execute(stmt)).all()

    by_date = {}
    for row in rows:
        # row.day may be a string in SQLite or a date object in PostgreSQL
        row_date = row.day if isinstance(row.day, date) else date.fromisoformat(str(row.day))
        by_date[row_date] = {
            "date": row_date,
            "total_calories": int(row.calories),
            "total_protein_g": float(row.protein),
            "total_fat_g": float(row.fat),
            "total_carbs_g": float(row.carbs),
            "goal_calories": user.daily_cal_goal,
            "goal_protein_g": user.daily_protein_goal_g,
            "goal_fat_g": user.daily_fat_goal_g,
            "goal_carbs_g": user.daily_carbs_goal_g,
            "entry_count": row.entry_count,
        }

    days = []
    current = start
    while current <= end:
        if current in by_date:
            days.append(by_date[current])
        else:
            days.append({
                "date": current,
                "total_calories": 0,
                "total_protein_g": 0.0,
                "total_fat_g": 0.0,
                "total_carbs_g": 0.0,
                "goal_calories": user.daily_cal_goal,
                "goal_protein_g": user.daily_protein_goal_g,
                "goal_fat_g": user.daily_fat_goal_g,
                "goal_carbs_g": user.daily_carbs_goal_g,
                "entry_count": 0,
            })
        current += timedelta(days=1)
    return {"days": days}
