from unittest.mock import patch
from tests.conftest import make_jwt_payload, make_active_user


async def test_update_weight(client, db):
    user, sid = await make_active_user(db)

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.post("/api/v1/weight", json={"weight_kg": 75.0},
                                 headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    logged_date = resp.json()["date"]

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.put(f"/api/v1/weight/{logged_date}",
                                json={"weight_kg": 74.5},
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    assert resp.json()["weight_kg"] == 74.5


async def test_update_weight_not_found(client, db):
    user, sid = await make_active_user(db)

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.put("/api/v1/weight/2026-01-01",
                                json={"weight_kg": 70.0},
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 404
