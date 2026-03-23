import random
from datetime import date, time, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.models import User, FoodEntry, CatUnlock, EatingWindow

# --- Cat definitions ---
CATS = [
    {"name": "whiskers", "emoji": "😺", "unlock_streak": 0},
    {"name": "luna", "emoji": "🐱", "unlock_streak": 7},
    {"name": "mochi", "emoji": "😸", "unlock_streak": 14},
    {"name": "shadow", "emoji": "🙀", "unlock_streak": 21},
    {"name": "coco", "emoji": "😻", "unlock_streak": 30},
    {"name": "midnight", "emoji": "🐈‍⬛", "unlock_streak": 60},
]

# --- Mood logic ---
def compute_mood(calorie_pct: float) -> str:
    if calorie_pct >= 0.95:
        return "ecstatic"
    if calorie_pct >= 0.75:
        return "happy"
    if calorie_pct >= 0.50:
        return "meh"
    if calorie_pct > 0:
        return "sad"
    return "hungry"

# --- Time-of-day state ---
def get_time_of_day_state(now_time: time, windows: list[dict]) -> str:
    w_map = {w["meal_type"]: w for w in windows}
    bf = w_map.get("breakfast")
    lu = w_map.get("lunch")
    di = w_map.get("dinner")

    if now_time >= time(22, 0):
        return "LATE_NIGHT"
    if now_time < time(5, 0):
        return "DEEP_NIGHT"
    if bf and now_time < bf["start"]:
        return "EARLY_MORNING"
    if bf and bf["start"] <= now_time <= bf["end"]:
        return "BREAKFAST_WINDOW"
    if lu and now_time < lu["start"]:
        return "MID_MORNING"
    if lu and lu["start"] <= now_time <= lu["end"]:
        return "LUNCH_WINDOW"
    if di and now_time < di["start"]:
        return "AFTERNOON"
    if di and di["start"] <= now_time <= di["end"]:
        return "DINNER_WINDOW"
    if di and now_time > di["end"] and now_time < time(22, 0):
        return "EVENING_WIND_DOWN"
    return "AFTERNOON"

# --- Static message banks ---
MESSAGES = {
    "GOOD_PROGRESS": [
        "Looking solid today 🐾",
        "You're doing really well — keep it going",
        "Nice work today. Almost there",
        "The macros are looking good. Dinner should be easy",
        "Consistent day. This is how it's done",
        "On track. Nothing to stress about",
    ],
    "OVER_GOAL": [
        "Went a bit over today — happens to everyone",
        "Today was a hungry day. That's okay",
        "Over the goal, but tomorrow is fresh",
        "Bodies need different things on different days 🐱",
    ],
    "NEUTRAL": [
        "Still some room in the day — no rush",
        "Day's going fine. Just keep logging",
        "You've got this. One meal at a time",
        "Progress is progress 🐾",
    ],
    "LATE_NIGHT": [
        "Rest up. Tomorrow's a fresh start",
        "Today was what it was. See you tomorrow",
        "Not every day gets logged and that's okay",
    ],
    "DEEP_NIGHT": [
        "Still up? Rest well.",
        "Late night. See you in the morning.",
        "Sleep tight.",
    ],
    "EARLY_MORNING": [
        "Good morning. Breakfast window opens soon",
        "Still waking up... breakfast is almost here",
        "Ready when you are",
    ],
}

_last_msg: dict[str, str] = {}

def pick_message(pool: str) -> str:
    msgs = MESSAGES[pool]
    last = _last_msg.get(pool)
    choices = [m for m in msgs if m != last] or msgs
    msg = random.choice(choices)
    _last_msg[pool] = msg
    return msg


def select_message(calorie_pct: float, tod_state: str) -> tuple[str, str]:
    """Returns (message, message_type)."""
    if tod_state in ("LATE_NIGHT",):
        return pick_message("LATE_NIGHT"), "static"
    if tod_state == "DEEP_NIGHT":
        return pick_message("DEEP_NIGHT"), "static"
    if tod_state == "EARLY_MORNING":
        return pick_message("EARLY_MORNING"), "static"
    if calorie_pct > 1.0:
        return pick_message("OVER_GOAL"), "static"
    if calorie_pct >= 0.7:
        return pick_message("GOOD_PROGRESS"), "static"
    return pick_message("NEUTRAL"), "static"


# --- Streak logic ---
async def update_streak_on_entry(db: AsyncSession, user: User, today: date) -> None:
    if user.last_log_date == today:
        return
    if user.last_log_date and (today - user.last_log_date).days == 1:
        user.current_streak += 1
    elif user.last_log_date and (today - user.last_log_date).days > 1:
        user.current_streak = 1
    else:
        user.current_streak = 1
    user.last_log_date = today
    if user.current_streak > user.longest_streak:
        user.longest_streak = user.current_streak
    await _check_unlock(db, user)


async def _check_unlock(db: AsyncSession, user: User) -> None:
    for cat in CATS:
        if cat["unlock_streak"] <= user.current_streak:
            existing = await db.execute(
                select(CatUnlock).where(
                    CatUnlock.user_id == user.id,
                    CatUnlock.cat_name == cat["name"],
                )
            )
            if not existing.scalar_one_or_none():
                db.add(CatUnlock(user_id=user.id, cat_name=cat["name"]))


async def get_daily_calorie_pct(db: AsyncSession, user: User, today: date) -> float:
    stmt = select(func.coalesce(func.sum(FoodEntry.total_calories), 0)).where(
        FoodEntry.user_id == user.id,
        func.date(FoodEntry.logged_at) == today,
    )
    result = await db.execute(stmt)
    total = result.scalar()
    goal = user.daily_cal_goal or 2000
    return total / goal


async def get_eating_windows_for_user(db: AsyncSession, user_id) -> list[dict]:
    result = await db.execute(
        select(EatingWindow).where(EatingWindow.user_id == user_id)
    )
    windows = result.scalars().all()
    if not windows:
        return [
            {"meal_type": "breakfast", "start": time(7, 0), "end": time(9, 0)},
            {"meal_type": "lunch", "start": time(12, 0), "end": time(14, 0)},
            {"meal_type": "dinner", "start": time(18, 0), "end": time(20, 0)},
        ]
    return [{"meal_type": w.meal_type, "start": w.start_time, "end": w.end_time} for w in windows]
