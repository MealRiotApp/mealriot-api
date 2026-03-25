import pytest
from unittest.mock import patch
from tests.conftest import make_jwt_payload, make_active_user
from app.models.models import WaterLog, FoodEntry
from sqlalchemy import select


@pytest.mark.asyncio
async def test_mixed_food_and_drink_creates_two_entries(client, db):
    """Text with food + drink creates separate entries."""
    user, sid = await make_active_user(db)
    payload = make_jwt_payload(user.email, sid)

    items = [
        {"food_name": "Chicken Wings", "food_name_he": "כנפי עוף", "grams": 200, "calories": 400, "protein_g": 30, "fat_g": 25, "carbs_g": 5, "confidence": "medium", "is_drink": False},
        {"food_name": "Basil Smash Cocktail", "food_name_he": "קוקטייל בזיליקום", "grams": 200, "calories": 180, "protein_g": 0, "fat_g": 0, "carbs_g": 15, "confidence": "medium", "is_drink": True, "volume_ml": 200, "water_pct": 70},
    ]

    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.post("/api/v1/entries", headers={"Authorization": "Bearer fake"}, json={
            "description": "Chicken wings and basil smash cocktail",
            "source": "text", "meal_type": "dinner", "items": items,
        })
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["entries"]) == 2

    food_entry = next(e for e in data["entries"] if e["source"] == "text")
    drink_entry = next(e for e in data["entries"] if e["source"] == "drink")
    assert food_entry["total_calories"] == 400
    assert drink_entry["total_calories"] == 180

    # Water tracked for cocktail: 200 * 70% = 140ml
    result = await db.execute(select(WaterLog).where(WaterLog.user_id == user.id))
    wl = result.scalar_one_or_none()
    assert wl is not None
    assert wl.amount_ml == 140


@pytest.mark.asyncio
async def test_only_food_creates_single_entry(client, db):
    """All-food input creates single entry, no water change."""
    user, sid = await make_active_user(db)
    payload = make_jwt_payload(user.email, sid)

    items = [
        {"food_name": "Salad", "grams": 200, "calories": 100, "protein_g": 3, "fat_g": 2, "carbs_g": 10, "confidence": "medium"},
    ]

    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.post("/api/v1/entries", headers={"Authorization": "Bearer fake"}, json={
            "description": "Salad", "source": "text", "meal_type": "lunch", "items": items,
        })
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["entries"]) == 1
    assert data["entries"][0]["source"] == "text"
    assert data["drink_suggestions"] == []

    result = await db.execute(select(WaterLog).where(WaterLog.user_id == user.id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_only_drinks_creates_drink_entry(client, db):
    """All-drinks input creates single drink entry with water."""
    user, sid = await make_active_user(db)
    payload = make_jwt_payload(user.email, sid)

    items = [
        {"food_name": "Americano", "food_name_he": "אמריקנו", "grams": 250, "calories": 5, "protein_g": 0.3, "fat_g": 0, "carbs_g": 0, "confidence": "medium", "is_drink": True, "volume_ml": 250, "water_pct": 95},
    ]

    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.post("/api/v1/entries", headers={"Authorization": "Bearer fake"}, json={
            "description": "Americano", "source": "text", "meal_type": "snack", "items": items,
        })
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["entries"]) == 1
    assert data["entries"][0]["source"] == "drink"

    # Water: 250 * 95% = 237.5 -> round = 238
    result = await db.execute(select(WaterLog).where(WaterLog.user_id == user.id))
    wl = result.scalar_one()
    assert wl.amount_ml == 238  # round(250 * 95 / 100)


@pytest.mark.asyncio
async def test_drink_suggestions_in_response(client, db):
    """Response includes drink_suggestions for detected drinks."""
    user, sid = await make_active_user(db)
    payload = make_jwt_payload(user.email, sid)

    items = [
        {"food_name": "Latte", "food_name_he": "לאטה", "grams": 300, "calories": 120, "protein_g": 6, "fat_g": 4, "carbs_g": 12, "confidence": "medium", "is_drink": True, "volume_ml": 300, "water_pct": 85},
    ]

    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.post("/api/v1/entries", headers={"Authorization": "Bearer fake"}, json={
            "description": "Latte", "source": "text", "meal_type": "snack", "items": items,
        })
    data = resp.json()
    assert len(data["drink_suggestions"]) == 1
    s = data["drink_suggestions"][0]
    assert s["name"] == "Latte"
    assert s["volume_ml"] == 300
    assert s["water_pct"] == 85


@pytest.mark.asyncio
async def test_delete_drink_entry_from_split_subtracts_water(client, db):
    """Deleting the drink entry from a split subtracts water correctly."""
    user, sid = await make_active_user(db)
    payload = make_jwt_payload(user.email, sid)

    items = [
        {"food_name": "Wings", "grams": 200, "calories": 400, "protein_g": 30, "fat_g": 25, "carbs_g": 5, "confidence": "medium"},
        {"food_name": "Beer", "food_name_he": "בירה", "grams": 500, "calories": 200, "protein_g": 1, "fat_g": 0, "carbs_g": 15, "confidence": "medium", "is_drink": True, "volume_ml": 500, "water_pct": 92},
    ]

    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.post("/api/v1/entries", headers={"Authorization": "Bearer fake"}, json={
            "description": "Wings and beer", "source": "text", "meal_type": "dinner", "items": items,
        })
        drink_entry = next(e for e in resp.json()["entries"] if e["source"] == "drink")

        # Verify water was added
        result = await db.execute(select(WaterLog).where(WaterLog.user_id == user.id))
        wl = result.scalar_one()
        assert wl.amount_ml == 460  # 500 * 92%

        # Delete drink entry
        resp = await client.delete(f"/api/v1/entries/{drink_entry['id']}", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 204

    await db.refresh(wl)
    assert wl.amount_ml == 0
