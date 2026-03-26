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
    data = resp.json()["entries"][0]
    assert data["total_calories"] == 79
    assert data["description"] == "Bread"


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
        entry_id = create_resp.json()["entries"][0]["id"]

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
        entry_id = create_resp.json()["entries"][0]["id"]
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
    entry_id = create_resp.json()["entries"][0]["id"]

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user2.email, supabase_id=sid2)):
        del_resp = await client.delete(f"/api/v1/entries/{entry_id}",
                                       headers={"Authorization": "Bearer faketoken"})
    assert del_resp.status_code == 404


async def test_create_multi_item_creates_separate_entries(client, db):
    user, sid = await make_active_user(db)

    body = {
        "description": "pizza and hummus",
        "source": "text",
        "meal_type": "lunch",
        "items": [
            {"food_name": "Pizza Slice", "food_name_he": "משולש פיצה", "grams": 80,
             "calories": 250, "protein_g": 10.0, "fat_g": 12.0, "carbs_g": 25.0,
             "confidence": "medium"},
            {"food_name": "Hummus", "food_name_he": "חומוס", "grams": 100,
             "calories": 170, "protein_g": 8.0, "fat_g": 10.0, "carbs_g": 14.0,
             "confidence": "medium"},
        ],
        "logged_at": "2026-03-26T12:00:00Z",
    }

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.post("/api/v1/entries", json=body,
                                 headers={"Authorization": "Bearer faketoken"})

    assert resp.status_code == 201
    entries = resp.json()["entries"]
    assert len(entries) == 2
    assert entries[0]["description"] == "Pizza Slice"
    assert entries[0]["total_calories"] == 250
    assert len(entries[0]["items"]) == 1
    assert entries[1]["description"] == "Hummus"
    assert entries[1]["total_calories"] == 170
    assert len(entries[1]["items"]) == 1


async def test_create_entry_with_quantity(client, db):
    user, sid = await make_active_user(db)

    body = {
        "description": "pizza slices",
        "source": "text",
        "meal_type": "lunch",
        "items": [
            {"food_name": "Pizza Slice", "food_name_he": "משולש פיצה", "grams": 80,
             "calories": 250, "protein_g": 10.0, "fat_g": 12.0, "carbs_g": 25.0,
             "confidence": "medium", "quantity": 3},
        ],
        "logged_at": "2026-03-26T12:00:00Z",
    }

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.post("/api/v1/entries", json=body,
                                 headers={"Authorization": "Bearer faketoken"})

    assert resp.status_code == 201
    entry = resp.json()["entries"][0]
    assert entry["description"] == "Pizza Slice x3"
    assert entry["total_calories"] == 750
    assert entry["total_protein_g"] == 30.0
    assert entry["total_fat_g"] == 36.0
    assert entry["total_carbs_g"] == 75.0


async def test_update_entry_regenerates_description(client, db):
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
        entry_id = create_resp.json()["entries"][0]["id"]

        updated_items = [{"food_name": "Rice", "food_name_he": "אורז", "grams": 200,
                          "calories": 260, "protein_g": 5.0, "fat_g": 0.5, "carbs_g": 57.0,
                          "confidence": "high"}]
        patch_resp = await client.patch(
            f"/api/v1/entries/{entry_id}",
            json={"items": updated_items},
            headers={"Authorization": "Bearer faketoken"},
        )

    assert patch_resp.status_code == 200
    assert patch_resp.json()["description"] == "Rice"


async def test_update_entry_with_quantity_regenerates_description(client, db):
    user, sid = await make_active_user(db)

    create_body = {
        "description": "pizza",
        "source": "text",
        "meal_type": "snack",
        "items": [{"food_name": "Pizza Slice", "food_name_he": "משולש פיצה", "grams": 80,
                   "calories": 250, "protein_g": 10.0, "fat_g": 12.0, "carbs_g": 25.0,
                   "confidence": "medium", "quantity": 3}],
    }

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        create_resp = await client.post("/api/v1/entries", json=create_body,
                                        headers={"Authorization": "Bearer faketoken"})
        entry_id = create_resp.json()["entries"][0]["id"]

        updated_items = [{"food_name": "Pizza Slice", "food_name_he": "משולש פיצה", "grams": 80,
                          "calories": 250, "protein_g": 10.0, "fat_g": 12.0, "carbs_g": 25.0,
                          "confidence": "medium", "quantity": 2}]
        patch_resp = await client.patch(
            f"/api/v1/entries/{entry_id}",
            json={"items": updated_items},
            headers={"Authorization": "Bearer faketoken"},
        )

    assert patch_resp.status_code == 200
    assert patch_resp.json()["description"] == "Pizza Slice x2"
    assert patch_resp.json()["total_calories"] == 500
