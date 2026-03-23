import pytest
from unittest.mock import patch
from tests.conftest import make_jwt_payload, make_active_user


async def test_create_entry(client, db):
    user, sid = await make_active_user(db)

    body = {
        "description": "a slice of bread",
        "source": "text",
        "meal_type": "breakfast",
        "items": [
            {"food_name": "Bread", "food_name_he": "לחם", "grams": 30,
             "calories": 79, "protein_g": 2.5, "fat_g": 0.8, "carbs_g": 15.1, "confidence": "high"}
        ],
        "logged_at": "2026-03-23T08:00:00Z",
    }

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.post("/api/v1/entries", json=body,
                                 headers={"Authorization": "Bearer faketoken"})

    assert resp.status_code == 201
    data = resp.json()
    assert data["total_calories"] == 79
    assert data["description"] == "a slice of bread"


async def test_list_entries_for_day(client, db):
    user, sid = await make_active_user(db)

    body = {
        "description": "lunch",
        "source": "text",
        "meal_type": "lunch",
        "items": [{"food_name": "Rice", "food_name_he": "אורז", "grams": 200,
                   "calories": 260, "protein_g": 5.0, "fat_g": 0.5, "carbs_g": 57.0,
                   "confidence": "high"}],
        "logged_at": "2026-03-23T12:00:00Z",
    }

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        await client.post("/api/v1/entries", json=body,
                          headers={"Authorization": "Bearer faketoken"})
        resp = await client.get("/api/v1/entries?date=2026-03-23",
                                headers={"Authorization": "Bearer faketoken"})

    assert resp.status_code == 200
    assert len(resp.json()["entries"]) == 1


async def test_update_entry_recalculates_totals(client, db):
    user, sid = await make_active_user(db)

    create_body = {
        "description": "bread",
        "source": "text",
        "meal_type": "snack",
        "items": [{"food_name": "Bread", "food_name_he": "לחם", "grams": 30,
                   "calories": 79, "protein_g": 2.5, "fat_g": 0.8, "carbs_g": 15.1,
                   "confidence": "high"}],
    }

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        create_resp = await client.post("/api/v1/entries", json=create_body,
                                        headers={"Authorization": "Bearer faketoken"})
        entry_id = create_resp.json()["id"]

        updated_items = [{"food_name": "Bread", "food_name_he": "לחם", "grams": 60,
                          "calories": 158, "protein_g": 5.0, "fat_g": 1.6, "carbs_g": 30.2,
                          "confidence": "high"}]
        patch_resp = await client.patch(
            f"/api/v1/entries/{entry_id}",
            json={"items": updated_items},
            headers={"Authorization": "Bearer faketoken"},
        )

    assert patch_resp.status_code == 200
    assert patch_resp.json()["total_calories"] == 158


async def test_delete_entry(client, db):
    user, sid = await make_active_user(db)

    create_body = {
        "description": "snack",
        "source": "text",
        "meal_type": "snack",
        "items": [{"food_name": "Apple", "food_name_he": "תפוח", "grams": 100,
                   "calories": 52, "protein_g": 0.3, "fat_g": 0.2, "carbs_g": 14.0,
                   "confidence": "high"}],
    }

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        create_resp = await client.post("/api/v1/entries", json=create_body,
                                        headers={"Authorization": "Bearer faketoken"})
        entry_id = create_resp.json()["id"]
        del_resp = await client.delete(f"/api/v1/entries/{entry_id}",
                                       headers={"Authorization": "Bearer faketoken"})

    assert del_resp.status_code == 204


async def test_recent_foods_upserted_on_create(client, db):
    from app.models.models import RecentFood
    from sqlalchemy import select

    user, sid = await make_active_user(db)

    body = {
        "description": "banana",
        "source": "text",
        "meal_type": "snack",
        "items": [{"food_name": "Banana", "food_name_he": "בננה", "grams": 120,
                   "calories": 107, "protein_g": 1.3, "fat_g": 0.4, "carbs_g": 27.5,
                   "confidence": "high"}],
    }

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        await client.post("/api/v1/entries", json=body,
                          headers={"Authorization": "Bearer faketoken"})

    result = await db.execute(
        select(RecentFood).where(RecentFood.user_id == user.id,
                                 RecentFood.food_name == "banana")
    )
    recent = result.scalar_one_or_none()
    assert recent is not None
    assert recent.use_count == 1


async def test_cannot_access_other_users_entry(client, db):
    user1, sid1 = await make_active_user(db, email="user1@test.com")
    user2, sid2 = await make_active_user(db, email="user2@test.com")

    body = {
        "description": "private meal",
        "source": "text",
        "meal_type": "lunch",
        "items": [{"food_name": "Steak", "food_name_he": "סטייק", "grams": 200,
                   "calories": 400, "protein_g": 50.0, "fat_g": 20.0, "carbs_g": 0.0,
                   "confidence": "high"}],
    }

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user1.email, supabase_id=sid1)):
        create_resp = await client.post("/api/v1/entries", json=body,
                                        headers={"Authorization": "Bearer faketoken"})
    entry_id = create_resp.json()["id"]

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user2.email, supabase_id=sid2)):
        del_resp = await client.delete(f"/api/v1/entries/{entry_id}",
                                       headers={"Authorization": "Bearer faketoken"})
    assert del_resp.status_code == 404
