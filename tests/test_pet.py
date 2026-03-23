import pytest
from datetime import time
from unittest.mock import patch
from tests.conftest import make_jwt_payload, make_active_user
from app.services.pet_service import compute_mood, get_time_of_day_state, CATS


def test_mood_thresholds():
    assert compute_mood(1.0) == "ecstatic"
    assert compute_mood(0.95) == "ecstatic"
    assert compute_mood(0.80) == "happy"
    assert compute_mood(0.60) == "meh"
    assert compute_mood(0.30) == "sad"
    assert compute_mood(0.0) == "hungry"


def test_time_of_day_states():
    windows = [
        {"meal_type": "breakfast", "start": time(7, 0), "end": time(9, 0)},
        {"meal_type": "lunch", "start": time(12, 0), "end": time(14, 0)},
        {"meal_type": "dinner", "start": time(18, 0), "end": time(20, 0)},
    ]
    assert get_time_of_day_state(time(6, 30), windows) == "EARLY_MORNING"
    assert get_time_of_day_state(time(8, 0), windows) == "BREAKFAST_WINDOW"
    assert get_time_of_day_state(time(10, 0), windows) == "MID_MORNING"
    assert get_time_of_day_state(time(13, 0), windows) == "LUNCH_WINDOW"
    assert get_time_of_day_state(time(16, 0), windows) == "AFTERNOON"
    assert get_time_of_day_state(time(19, 0), windows) == "DINNER_WINDOW"
    assert get_time_of_day_state(time(21, 0), windows) == "EVENING_WIND_DOWN"
    assert get_time_of_day_state(time(22, 30), windows) == "LATE_NIGHT"
    assert get_time_of_day_state(time(3, 0), windows) == "DEEP_NIGHT"


async def test_pet_status(client, db):
    user, sid = await make_active_user(db)
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.get("/api/v1/pet/status",
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["mood"] == "hungry"
    assert data["active_cat"] == "whiskers"
    assert data["current_streak"] == 0


async def test_collection(client, db):
    user, sid = await make_active_user(db)
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.get("/api/v1/pet/collection",
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["cats"]) == 6
    assert data["active_cat"] == "whiskers"


async def test_set_active_cat_not_unlocked(client, db):
    user, sid = await make_active_user(db)
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.post("/api/v1/pet/active-cat",
                                 json={"cat_name": "luna"},
                                 headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "CAT_NOT_UNLOCKED"


async def test_eating_windows_default(client, db):
    user, sid = await make_active_user(db)
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.get("/api/v1/pet/eating-windows",
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    assert len(resp.json()["windows"]) == 3


async def test_update_eating_windows(client, db):
    user, sid = await make_active_user(db)
    windows = [
        {"meal_type": "breakfast", "start_time": "08:00", "end_time": "10:00"},
        {"meal_type": "lunch", "start_time": "13:00", "end_time": "14:30"},
        {"meal_type": "dinner", "start_time": "19:00", "end_time": "21:00"},
    ]
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.put("/api/v1/pet/eating-windows",
                                json={"windows": windows},
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["windows"][0]["start_time"] == "08:00"


async def test_streak_increments_on_entry(client, db):
    user, sid = await make_active_user(db)
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        await client.post("/api/v1/entries", json={
            "description": "toast",
            "source": "text",
            "meal_type": "breakfast",
            "items": [{"food_name": "Toast", "grams": 50, "calories": 130,
                        "protein_g": 3, "fat_g": 1, "carbs_g": 25, "confidence": "high"}],
        }, headers={"Authorization": "Bearer faketoken"})
        resp = await client.get("/api/v1/pet/status",
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.json()["current_streak"] == 1


async def test_message_endpoint(client, db):
    user, sid = await make_active_user(db)
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.post("/api/v1/pet/message",
                                 headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    assert resp.json()["message_type"] in ("static", "ai")
