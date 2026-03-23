from datetime import datetime, timezone, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.models import User, FoodEntry, WaterLog

MAX_UPDATES_PER_DAY = 3
MIN_HOURS_BETWEEN_UPDATES = 4


async def should_update_summary(user: User) -> bool:
    if not user.summary_updated_at:
        return True
    now = datetime.now(timezone.utc)
    hours_since = (now - user.summary_updated_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
    return hours_since >= MIN_HOURS_BETWEEN_UPDATES


async def build_daily_summary(db: AsyncSession, user: User) -> str:
    today = date.today()

    # Get today's entries
    result = await db.execute(
        select(FoodEntry).where(
            FoodEntry.user_id == user.id,
            func.date(FoodEntry.logged_at) == today,
        ).order_by(FoodEntry.logged_at)
    )
    entries = result.scalars().all()

    # Get water
    water_result = await db.execute(
        select(WaterLog).where(WaterLog.user_id == user.id, WaterLog.date == today)
    )
    water = water_result.scalar_one_or_none()
    water_ml = water.amount_ml if water else 0

    # Build summary
    total_cal = sum(e.total_calories for e in entries)
    total_protein = sum(float(e.total_protein_g) for e in entries)
    total_fat = sum(float(e.total_fat_g) for e in entries)
    total_carbs = sum(float(e.total_carbs_g) for e in entries)

    cal_goal = user.daily_cal_goal or 2000
    protein_goal = user.daily_protein_goal_g or 120
    water_goal = user.daily_water_goal_ml or 2000

    foods = [e.description for e in entries]
    food_list = ", ".join(foods) if foods else "nothing yet"

    hour = datetime.now().hour
    time_of_day = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"

    summary = (
        f"Time: {time_of_day}. "
        f"Ate today: {food_list}. "
        f"Calories: {total_cal}/{cal_goal} ({round(total_cal/cal_goal*100)}%). "
        f"Protein: {round(total_protein)}g/{protein_goal}g. "
        f"Fat: {round(total_fat)}g. Carbs: {round(total_carbs)}g. "
        f"Water: {water_ml}ml/{water_goal}ml. "
        f"Entries: {len(entries)}. "
        f"Streak: {user.current_streak} days."
    )

    if user.goal_weight_kg and user.weight_kg:
        diff = float(user.weight_kg) - float(user.goal_weight_kg)
        if diff > 0:
            summary += f" Trying to lose {round(diff, 1)}kg."
        elif diff < 0:
            summary += f" Trying to gain {round(abs(diff), 1)}kg."

    return summary


async def update_user_summary(db: AsyncSession, user: User) -> str | None:
    if not await should_update_summary(user):
        return user.daily_summary

    summary = await build_daily_summary(db, user)
    user.daily_summary = summary
    user.summary_updated_at = datetime.now(timezone.utc)
    await db.commit()
    return summary
