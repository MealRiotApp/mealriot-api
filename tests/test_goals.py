import uuid
from unittest.mock import patch, AsyncMock

import pytest
from tests.conftest import make_jwt_payload, make_active_user


async def test_calculate_flexible_preset(client, db):
    """Flexible preset: protein 0.8g/kg, fat 30%, carbs remainder."""
    user, sid = await make_active_user(db, "flex@test.com")
    payload = make_jwt_payload("flex@test.com", sid)

    body = {
        "weight_kg": 70,
        "height_cm": 170,
        "age": 30,
        "sex": "male",
        "activity_level": "moderate",
        "goal": "maintain",
        "macro_preset": "flexible",
    }

    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.post("/api/v1/goals/calculate", json=body, headers={"Authorization": "Bearer fake"})

    assert resp.status_code == 200
    data = resp.json()

    # Protein: 0.8 * 70 = 56g
    assert data["daily_protein_goal_g"] == 56

    # Fat: 30% of daily_cal / 9
    daily_cal = data["daily_cal_goal"]
    expected_fat = round(daily_cal * 0.30 / 9)
    assert data["daily_fat_goal_g"] == expected_fat

    # Carbs: remainder
    remaining_cal = daily_cal - (56 * 4) - (expected_fat * 9)
    expected_carbs = max(50, round(remaining_cal / 4))
    assert data["daily_carbs_goal_g"] == expected_carbs


async def test_calculate_persists_quiz_fields(client, db):
    """Quiz submission should persist sex, goal, body_fat_pct, macro_preset."""
    user, sid = await make_active_user(db, "persist@test.com")
    payload = make_jwt_payload("persist@test.com", sid)

    body = {
        "weight_kg": 80,
        "height_cm": 180,
        "age": 25,
        "sex": "female",
        "activity_level": "active",
        "goal": "moderate_loss",
        "body_fat_pct": 22.5,
        "macro_preset": "balanced",
    }

    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.post("/api/v1/goals/calculate", json=body, headers={"Authorization": "Bearer fake"})

    assert resp.status_code == 200

    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        profile_resp = await client.get("/api/v1/profile", headers={"Authorization": "Bearer fake"})

    profile = profile_resp.json()
    assert profile["sex"] == "female"
    assert profile["goal"] == "moderate_loss"
    assert float(profile["body_fat_pct"]) == 22.5
    assert profile["macro_preset"] == "balanced"
    assert profile["activity_level"] == "active"
