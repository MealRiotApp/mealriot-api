from datetime import date

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import DailyPoints, FoodEntry, User


def calc_calorie_points(total_cal: int, goal: int) -> int:
    if goal == 0:
        return 0
    pct = total_cal / goal
    if 0.9 <= pct <= 1.1:
        return 6
    if 0.75 <= pct < 0.9:
        return 4
    if 1.1 < pct <= 1.25:
        return 3
    if 0.5 <= pct < 0.75:
        return 2
    if pct > 1.25:
        return 1
    return 0


def calc_macro_points(
    protein: float, fat: float, carbs: float,
    protein_goal: int | None, fat_goal: int | None, carbs_goal: int | None,
    macro_bonus_enabled: bool,
) -> int:
    if not macro_bonus_enabled:
        return 0
    pts = 0
    if protein_goal and protein_goal > 0:
        if 0.85 <= protein / protein_goal <= 1.15:
            pts += 1
    other_hit = False
    if fat_goal and fat_goal > 0:
        if 0.85 <= fat / fat_goal <= 1.15:
            other_hit = True
    if not other_hit and carbs_goal and carbs_goal > 0:
        if 0.85 <= carbs / carbs_goal <= 1.15:
            other_hit = True
    if other_hit:
        pts += 1
    return pts


async def recalculate_daily_points(
    db: AsyncSession, user: User, target_date: date | None = None,
) -> DailyPoints:
    """Aggregate today's entries and upsert DailyPoints for the user."""
    day = target_date or date.today()

    result = await db.execute(
        select(
            func.coalesce(func.sum(FoodEntry.total_calories), 0),
            func.coalesce(func.sum(FoodEntry.total_protein_g), 0),
            func.coalesce(func.sum(FoodEntry.total_fat_g), 0),
            func.coalesce(func.sum(FoodEntry.total_carbs_g), 0),
            func.count(FoodEntry.id),
        ).where(
            FoodEntry.user_id == user.id,
            func.date(FoodEntry.logged_at) == day,
        )
    )
    row = result.one()
    total_cal = int(row[0])
    total_protein = float(row[1])
    total_fat = float(row[2])
    total_carbs = float(row[3])
    entry_count = int(row[4])

    goal = user.daily_cal_goal or 2000
    cal_pts = calc_calorie_points(total_cal, goal)
    log_pts = min(entry_count, 2)
    macro_pts = calc_macro_points(
        protein=total_protein, fat=total_fat, carbs=total_carbs,
        protein_goal=user.daily_protein_goal_g,
        fat_goal=user.daily_fat_goal_g,
        carbs_goal=user.daily_carbs_goal_g,
        macro_bonus_enabled=user.macro_bonus_enabled if user.macro_bonus_enabled is not None else True,
    )
    total_pts = cal_pts + log_pts + macro_pts

    existing = await db.execute(
        select(DailyPoints).where(
            DailyPoints.user_id == user.id, DailyPoints.date == day,
        )
    )
    dp = existing.scalar_one_or_none()
    if dp:
        dp.calorie_points = cal_pts
        dp.logging_points = log_pts
        dp.macro_points = macro_pts
        dp.total_points = total_pts
    else:
        dp = DailyPoints(
            user_id=user.id, date=day,
            calorie_points=cal_pts, logging_points=log_pts,
            macro_points=macro_pts, total_points=total_pts,
        )
        db.add(dp)

    await db.flush()
    return dp
