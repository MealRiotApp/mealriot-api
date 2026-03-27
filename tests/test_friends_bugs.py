from unittest.mock import patch
from tests.conftest import make_jwt_payload, make_active_user


async def test_cannot_friend_self(client, db):
    user, sid = await make_active_user(db)
    user.username = "self_user"
    await db.commit()

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.post("/api/v1/friends/request",
                                 json={"username": "self_user"},
                                 headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "CANNOT_FRIEND_SELF"


async def test_search_excludes_self(client, db):
    user, sid = await make_active_user(db)
    user.username = "myself"
    await db.commit()

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.get("/api/v1/friends/search?username=myself",
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    assert resp.json()["result"] is None
