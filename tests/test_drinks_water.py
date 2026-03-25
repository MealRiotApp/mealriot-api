import pytest
from unittest.mock import patch
from tests.conftest import make_jwt_payload, make_active_user
from app.models.models import CustomDrink, WaterLog
from sqlalchemy import select


async def _create_user_with_drink(db, **drink_overrides):
    """Helper: create active user + a test drink, return (user, sid, drink)."""
    user, sid = await make_active_user(db)
    defaults = dict(
        user_id=user.id, name="Test Beer", name_he="בירה",
        icon="🍺", volume_ml=500, calories=200,
        sugar_g=0, protein_g=1, fat_g=0, carbs_g=15,
        counts_as_water=True, water_pct=92,
        is_default=False, use_count=0,
    )
    defaults.update(drink_overrides)
    drink = CustomDrink(**defaults)
    db.add(drink)
    await db.commit()
    await db.refresh(drink)
    return user, sid, drink


# --- Task 4: Default drink seeding ---

@pytest.mark.asyncio
async def test_new_user_gets_default_water_drink(client, db):
    payload = make_jwt_payload("newuser@test.com")
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        await client.get("/api/v1/drinks", headers={"Authorization": "Bearer fake"})

    result = await db.execute(select(CustomDrink).where(CustomDrink.is_default == True))
    default_drink = result.scalar_one_or_none()
    assert default_drink is not None
    assert default_drink.name == "Glass of Water"
    assert default_drink.volume_ml == 250
    assert default_drink.water_pct == 100
    assert default_drink.is_default is True


# --- Task 5: Log drink endpoint ---

@pytest.mark.asyncio
async def test_log_drink_creates_entry_and_adds_water(client, db):
    user, sid, drink = await _create_user_with_drink(db)
    payload = make_jwt_payload(user.email, sid)

    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.post(
            f"/api/v1/drinks/{drink.id}/log",
            headers={"Authorization": "Bearer fake"},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["source"] == "drink"
    assert data["drink_id"] == str(drink.id)
    assert data["total_calories"] == 200

    # 500 * 92 / 100 = 460ml
    result = await db.execute(select(WaterLog).where(WaterLog.user_id == user.id))
    wl = result.scalar_one_or_none()
    assert wl is not None
    assert wl.amount_ml == 460


@pytest.mark.asyncio
async def test_log_drink_increments_use_count(client, db):
    user, sid, drink = await _create_user_with_drink(db)
    payload = make_jwt_payload(user.email, sid)

    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        await client.post(f"/api/v1/drinks/{drink.id}/log", headers={"Authorization": "Bearer fake"})
        await client.post(f"/api/v1/drinks/{drink.id}/log", headers={"Authorization": "Bearer fake"})

    await db.refresh(drink)
    assert drink.use_count == 2


@pytest.mark.asyncio
async def test_log_drink_counts_as_water_false(client, db):
    user, sid, drink = await _create_user_with_drink(db, counts_as_water=False, water_pct=60, name="Whiskey", icon="🥃", volume_ml=50, calories=110)
    payload = make_jwt_payload(user.email, sid)

    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.post(f"/api/v1/drinks/{drink.id}/log", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 201

    result = await db.execute(select(WaterLog).where(WaterLog.user_id == user.id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_log_drink_source_is_drink(client, db):
    user, sid, drink = await _create_user_with_drink(db)
    payload = make_jwt_payload(user.email, sid)

    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.post(f"/api/v1/drinks/{drink.id}/log", headers={"Authorization": "Bearer fake"})
    assert resp.json()["source"] == "drink"


# --- Task 6: Water subtraction on delete ---

@pytest.mark.asyncio
async def test_delete_drink_entry_subtracts_water(client, db):
    user, sid, drink = await _create_user_with_drink(db)
    payload = make_jwt_payload(user.email, sid)

    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.post(f"/api/v1/drinks/{drink.id}/log", headers={"Authorization": "Bearer fake"})
        entry_id = resp.json()["id"]

        result = await db.execute(select(WaterLog).where(WaterLog.user_id == user.id))
        wl = result.scalar_one()
        assert wl.amount_ml == 460

        resp = await client.delete(f"/api/v1/entries/{entry_id}", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 204

    await db.refresh(wl)
    assert wl.amount_ml == 0


@pytest.mark.asyncio
async def test_delete_entry_water_floors_at_zero(client, db):
    user, sid, drink = await _create_user_with_drink(db)
    payload = make_jwt_payload(user.email, sid)

    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.post(f"/api/v1/drinks/{drink.id}/log", headers={"Authorization": "Bearer fake"})
        entry_id = resp.json()["id"]

        result = await db.execute(select(WaterLog).where(WaterLog.user_id == user.id))
        wl = result.scalar_one()
        wl.amount_ml = 100  # less than 460ml drink water
        await db.commit()

        resp = await client.delete(f"/api/v1/entries/{entry_id}", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 204

    await db.refresh(wl)
    assert wl.amount_ml == 0


@pytest.mark.asyncio
async def test_delete_non_drink_entry_no_water_change(client, db):
    user, sid = await make_active_user(db)
    payload = make_jwt_payload(user.email, sid)

    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.post("/api/v1/entries", headers={"Authorization": "Bearer fake"}, json={
            "description": "Salad",
            "source": "text",
            "meal_type": "lunch",
            "items": [{"food_name": "Salad", "grams": 200, "calories": 150, "protein_g": 5, "fat_g": 3, "carbs_g": 20, "confidence": "high"}],
        })
        entry_id = resp.json()["entries"][0]["id"]
        resp = await client.delete(f"/api/v1/entries/{entry_id}", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 204


# --- Task 7: Sort + block default deletion ---

@pytest.mark.asyncio
async def test_drinks_sorted_by_default_then_use_count(client, db):
    user, sid = await make_active_user(db)
    drinks_data = [
        ("Water", True, 5, "💧"),
        ("Coffee", False, 10, "☕"),
        ("Beer", False, 3, "🍺"),
        ("Juice", False, 10, "🧃"),
    ]
    for name, is_default, use_count, icon in drinks_data:
        db.add(CustomDrink(
            user_id=user.id, name=name, icon=icon,
            volume_ml=250, calories=0, sugar_g=0, protein_g=0,
            fat_g=0, carbs_g=0, counts_as_water=True, water_pct=100,
            is_default=is_default, use_count=use_count,
        ))
    await db.commit()
    payload = make_jwt_payload(user.email, sid)

    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.get("/api/v1/drinks", headers={"Authorization": "Bearer fake"})
    names = [d["name"] for d in resp.json()]
    assert names == ["Water", "Coffee", "Juice", "Beer"]


@pytest.mark.asyncio
async def test_delete_default_drink_returns_400(client, db):
    user, sid = await make_active_user(db)
    drink = CustomDrink(
        user_id=user.id, name="Water", icon="💧",
        volume_ml=250, calories=0, sugar_g=0, protein_g=0,
        fat_g=0, carbs_g=0, counts_as_water=True, water_pct=100,
        is_default=True, use_count=0,
    )
    db.add(drink)
    await db.commit()
    await db.refresh(drink)
    payload = make_jwt_payload(user.email, sid)

    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.delete(f"/api/v1/drinks/{drink.id}", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 400
