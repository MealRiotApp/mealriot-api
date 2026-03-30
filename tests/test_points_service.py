from datetime import date, datetime, timezone

from sqlalchemy import select

from app.models.models import FoodEntry, DailyPoints
from app.services.points_service import calc_calorie_points, calc_macro_points
from tests.conftest import make_active_user


async def test_calorie_points_perfect():
    assert calc_calorie_points(1900, 2000) == 6  # 95% = in 90-110%


async def test_calorie_points_moderate_under():
    assert calc_calorie_points(1600, 2000) == 4  # 80% = in 75-89%


async def test_calorie_points_slight_over():
    assert calc_calorie_points(2300, 2000) == 3  # 115% = in 110-125%


async def test_calorie_points_low():
    assert calc_calorie_points(1200, 2000) == 2  # 60% = in 50-74%


async def test_calorie_points_way_over():
    assert calc_calorie_points(3000, 2000) == 1  # 150% = >125%


async def test_calorie_points_almost_nothing():
    assert calc_calorie_points(200, 2000) == 0  # 10% = <50%


async def test_calorie_points_zero_goal():
    assert calc_calorie_points(500, 0) == 0


async def test_macro_points_protein_hit():
    assert calc_macro_points(
        protein=110, fat=20, carbs=100,
        protein_goal=120, fat_goal=78, carbs_goal=180,
        macro_bonus_enabled=True,
    ) == 1


async def test_macro_points_protein_and_fat_hit():
    assert calc_macro_points(
        protein=115, fat=75, carbs=100,
        protein_goal=120, fat_goal=78, carbs_goal=180,
        macro_bonus_enabled=True,
    ) == 2


async def test_macro_points_protein_miss_carbs_hit():
    assert calc_macro_points(
        protein=50, fat=20, carbs=170,
        protein_goal=120, fat_goal=78, carbs_goal=180,
        macro_bonus_enabled=True,
    ) == 1


async def test_macro_points_disabled():
    assert calc_macro_points(
        protein=115, fat=75, carbs=170,
        protein_goal=120, fat_goal=78, carbs_goal=180,
        macro_bonus_enabled=False,
    ) == 0


async def test_macro_points_no_goals():
    assert calc_macro_points(
        protein=100, fat=50, carbs=200,
        protein_goal=None, fat_goal=None, carbs_goal=None,
        macro_bonus_enabled=True,
    ) == 0


async def test_recalculate_creates_daily_points(db):
    from app.services.points_service import recalculate_daily_points

    user, _ = await make_active_user(db)
    today = date(2026, 3, 30)

    db.add(FoodEntry(
        user_id=user.id, description="Rice", source="text",
        meal_type="lunch", items=[{"food_name": "Rice"}],
        total_calories=500, total_protein_g=10, total_fat_g=2, total_carbs_g=100,
        logged_at=datetime(2026, 3, 30, 12, 0, tzinfo=timezone.utc),
    ))
    await db.flush()

    dp = await recalculate_daily_points(db, user, target_date=today)

    assert dp.logging_points == 1
    assert dp.total_points > 0
    assert dp.user_id == user.id
    assert dp.date == today


async def test_recalculate_updates_existing_daily_points(db):
    from app.services.points_service import recalculate_daily_points

    user, _ = await make_active_user(db)
    today = date(2026, 3, 30)

    db.add(FoodEntry(
        user_id=user.id, description="Rice", source="text",
        meal_type="lunch", items=[{"food_name": "Rice"}],
        total_calories=500, total_protein_g=10, total_fat_g=2, total_carbs_g=100,
        logged_at=datetime(2026, 3, 30, 12, 0, tzinfo=timezone.utc),
    ))
    await db.flush()
    dp1 = await recalculate_daily_points(db, user, target_date=today)
    assert dp1.logging_points == 1

    db.add(FoodEntry(
        user_id=user.id, description="Chicken", source="text",
        meal_type="dinner", items=[{"food_name": "Chicken"}],
        total_calories=300, total_protein_g=30, total_fat_g=5, total_carbs_g=0,
        logged_at=datetime(2026, 3, 30, 18, 0, tzinfo=timezone.utc),
    ))
    await db.flush()
    dp2 = await recalculate_daily_points(db, user, target_date=today)

    assert dp2.logging_points == 2
    result = await db.execute(
        select(DailyPoints).where(DailyPoints.user_id == user.id, DailyPoints.date == today)
    )
    assert len(result.scalars().all()) == 1


async def test_recalculate_zero_entries(db):
    from app.services.points_service import recalculate_daily_points

    user, _ = await make_active_user(db)
    today = date(2026, 3, 30)

    dp = await recalculate_daily_points(db, user, target_date=today)
    assert dp.calorie_points == 0
    assert dp.logging_points == 0
    assert dp.macro_points == 0
    assert dp.total_points == 0


async def test_create_entry_triggers_points(db):
    from app.services.entries_service import create_entry

    user, _ = await make_active_user(db)
    today = date(2026, 3, 30)

    await create_entry(db, user, {
        "source": "text",
        "meal_type": "lunch",
        "items": [{"food_name": "Rice", "calories": 500, "protein_g": 10,
                    "fat_g": 2, "carbs_g": 100}],
        "logged_at": datetime(2026, 3, 30, 12, 0, tzinfo=timezone.utc),
    })

    result = await db.execute(
        select(DailyPoints).where(DailyPoints.user_id == user.id, DailyPoints.date == today)
    )
    dp = result.scalar_one()
    assert dp.logging_points == 1
    assert dp.total_points > 0


async def test_delete_entry_recalculates_points(db):
    from app.services.entries_service import create_entry, delete_entry

    user, _ = await make_active_user(db)
    today = date(2026, 3, 30)

    result = await create_entry(db, user, {
        "source": "text",
        "meal_type": "lunch",
        "items": [{"food_name": "Rice", "calories": 500, "protein_g": 10,
                    "fat_g": 2, "carbs_g": 100}],
        "logged_at": datetime(2026, 3, 30, 12, 0, tzinfo=timezone.utc),
    })
    entry_id = result["entries"][0].id

    await delete_entry(db, user.id, entry_id)

    dp_result = await db.execute(
        select(DailyPoints).where(DailyPoints.user_id == user.id, DailyPoints.date == today)
    )
    dp = dp_result.scalar_one()
    assert dp.logging_points == 0
    assert dp.total_points == 0


async def test_update_entry_recalculates_points(db):
    from app.services.entries_service import create_entry, update_entry

    user, _ = await make_active_user(db)
    today = date(2026, 3, 30)

    result = await create_entry(db, user, {
        "source": "text",
        "meal_type": "lunch",
        "items": [{"food_name": "Rice", "calories": 500, "protein_g": 10,
                    "fat_g": 2, "carbs_g": 100}],
        "logged_at": datetime(2026, 3, 30, 12, 0, tzinfo=timezone.utc),
    })
    entry_id = result["entries"][0].id

    await update_entry(db, user.id, entry_id, [
        {"food_name": "Big Rice", "calories": 1900, "protein_g": 40,
         "fat_g": 5, "carbs_g": 400},
    ])

    dp_result = await db.execute(
        select(DailyPoints).where(DailyPoints.user_id == user.id, DailyPoints.date == today)
    )
    dp = dp_result.scalar_one()
    # 1900 cal on 2000 goal = 95% = 6 calorie points
    assert dp.calorie_points == 6


async def test_goal_change_recalculates_points(db):
    from app.services.entries_service import create_entry
    from app.services.points_service import recalculate_daily_points

    user, _ = await make_active_user(db)
    today = date(2026, 3, 30)

    # Log entry with 1900 calories (95% of default 2000 goal = 6 cal pts)
    await create_entry(db, user, {
        "source": "text",
        "meal_type": "lunch",
        "items": [{"food_name": "Rice", "calories": 1900, "protein_g": 40,
                    "fat_g": 20, "carbs_g": 300}],
        "logged_at": datetime(2026, 3, 30, 12, 0, tzinfo=timezone.utc),
    })
    dp_result = await db.execute(
        select(DailyPoints).where(DailyPoints.user_id == user.id, DailyPoints.date == today)
    )
    dp = dp_result.scalar_one()
    assert dp.calorie_points == 6  # 95% of 2000

    # Change goal to 3000 — now 1900/3000 = 63.3% = 2 cal pts
    user.daily_cal_goal = 3000
    await db.flush()

    await recalculate_daily_points(db, user, target_date=today)
    await db.refresh(dp)

    assert dp.calorie_points == 2  # 63% of 3000


async def test_compute_daily_points_endpoint_removed(client):
    resp = await client.post(
        "/internal/jobs/compute-daily-points",
        headers={"x-internal-secret": "test"},
    )
    assert resp.status_code == 404
