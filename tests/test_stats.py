import pytest
from unittest.mock import patch
from tests.conftest import make_jwt_payload, make_active_user


async def _seed_entry(client, email, sid, logged_at: str, calories: int = 500):
    body = {
        "description": "meal",
        "source": "text",
        "meal_type": "lunch",
        "items": [{"food_name": "Food", "food_name_he": "אוכל", "grams": 100,
                   "calories": calories, "protein_g": 10.0, "fat_g": 5.0,
                   "carbs_g": 50.0, "confidence": "high"}],
        "logged_at": logged_at,
    }
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(email, supabase_id=sid)):
        return await client.post("/api/v1/entries", json=body,
                                 headers={"Authorization": "Bearer faketoken"})


async def test_daily_stats_no_entries(client, db):
    user, sid = await make_active_user(db)

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.get("/api/v1/stats/daily?date=2026-03-23",
                                headers={"Authorization": "Bearer faketoken"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_calories"] == 0
    assert data["goal_calories"] == 2000
    assert data["entries"] == []


async def test_daily_stats_with_entries(client, db):
    user, sid = await make_active_user(db)
    await _seed_entry(client, user.email, sid, "2026-03-23T08:00:00Z", calories=300)
    await _seed_entry(client, user.email, sid, "2026-03-23T12:00:00Z", calories=500)

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.get("/api/v1/stats/daily?date=2026-03-23",
                                headers={"Authorization": "Bearer faketoken"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_calories"] == 800
    assert len(data["entries"]) == 2


async def test_range_stats_with_entries(client, db):
    user, sid = await make_active_user(db)
    await _seed_entry(client, user.email, sid, "2026-03-22T12:00:00Z", calories=400)
    await _seed_entry(client, user.email, sid, "2026-03-23T12:00:00Z", calories=600)

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.get(
            "/api/v1/stats/range?start=2026-03-22&end=2026-03-23",
            headers={"Authorization": "Bearer faketoken"},
        )

    assert resp.status_code == 200
    days = resp.json()["days"]
    assert len(days) == 2
    cals = {d["date"]: d["total_calories"] for d in days}
    assert cals["2026-03-22"] == 400
    assert cals["2026-03-23"] == 600


async def test_range_stats_fills_empty_days(client, db):
    user, sid = await make_active_user(db)
    await _seed_entry(client, user.email, sid, "2026-03-22T12:00:00Z", calories=400)
    # March 23 intentionally has no entry

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.get(
            "/api/v1/stats/range?start=2026-03-22&end=2026-03-23",
            headers={"Authorization": "Bearer faketoken"},
        )

    assert resp.status_code == 200
    days = resp.json()["days"]
    assert len(days) == 2
    empty_day = next(d for d in days if d["date"] == "2026-03-23")
    assert empty_day["total_calories"] == 0
    assert empty_day["entry_count"] == 0
