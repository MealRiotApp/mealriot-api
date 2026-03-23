import pytest
from unittest.mock import patch
from tests.conftest import make_jwt_payload, make_active_user


async def test_get_profile(client, db):
    user, sid = await make_active_user(db)

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.get("/api/v1/profile",
                                headers={"Authorization": "Bearer faketoken"})

    assert resp.status_code == 200
    assert resp.json()["email"] == user.email
    assert resp.json()["daily_cal_goal"] == 2000


async def test_update_profile_language_and_theme(client, db):
    user, sid = await make_active_user(db)

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.patch(
            "/api/v1/profile",
            json={"language": "he", "theme": "midnight"},
            headers={"Authorization": "Bearer faketoken"},
        )

    assert resp.status_code == 200
    assert resp.json()["language"] == "he"
    assert resp.json()["theme"] == "midnight"


async def test_update_profile_goals(client, db):
    user, sid = await make_active_user(db)

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.patch(
            "/api/v1/profile",
            json={"daily_cal_goal": 1800, "daily_protein_goal_g": 100},
            headers={"Authorization": "Bearer faketoken"},
        )

    assert resp.status_code == 200
    assert resp.json()["daily_cal_goal"] == 1800
    assert resp.json()["daily_protein_goal_g"] == 100
