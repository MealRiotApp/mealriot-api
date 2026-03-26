import pytest
from unittest.mock import patch
from tests.conftest import make_jwt_payload, make_active_user


async def _create_entry(client, sid, email, description, logged_at):
    body = {
        "description": description,
        "source": "text",
        "meal_type": "lunch",
        "items": [{"food_name": description, "food_name_he": None, "grams": 100,
                   "calories": 200, "protein_g": 10, "fat_g": 5, "carbs_g": 30,
                   "confidence": "high"}],
        "logged_at": logged_at,
    }
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(email, supabase_id=sid)):
        resp = await client.post("/api/v1/entries", json=body,
                                 headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 201
    return resp.json()


async def test_entry_history_returns_entries(client, db):
    user, sid = await make_active_user(db)
    await _create_entry(client, sid, user.email, "Lunch", "2026-03-20T12:00:00Z")
    await _create_entry(client, sid, user.email, "Dinner", "2026-03-20T18:00:00Z")

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.get("/api/v1/entries/history?limit=10",
                                headers={"Authorization": "Bearer faketoken"})

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entries"]) == 2
    assert data["has_more"] is False
    assert data["entries"][0]["description"] == "Dinner"


async def test_entry_history_pagination(client, db):
    user, sid = await make_active_user(db)
    for i in range(5):
        await _create_entry(client, sid, user.email, f"Meal {i}",
                            f"2026-03-2{i}T12:00:00Z")

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.get("/api/v1/entries/history?limit=3",
                                headers={"Authorization": "Bearer faketoken"})

    data = resp.json()
    assert len(data["entries"]) == 3
    assert data["has_more"] is True
    assert data["next_cursor_time"] is not None
    assert data["next_cursor_id"] is not None

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp2 = await client.get(
            f"/api/v1/entries/history?limit=3&cursor_time={data['next_cursor_time']}&cursor_id={data['next_cursor_id']}",
            headers={"Authorization": "Bearer faketoken"})

    data2 = resp2.json()
    assert len(data2["entries"]) == 2
    assert data2["has_more"] is False
