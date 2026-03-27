from unittest.mock import patch
from tests.conftest import make_jwt_payload, make_active_user
from app.models.models import Friendship
from sqlalchemy import select


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


async def test_re_request_after_decline(client, db):
    # Create two users with usernames
    user_a, sid_a = await make_active_user(db, email="a@test.com")
    user_a.username = "user_a"
    user_b, sid_b = await make_active_user(db, email="b@test.com")
    user_b.username = "user_b"
    await db.commit()

    # Create a declined friendship: user_a requested, user_b declined
    friendship = Friendship(
        requester_id=user_a.id,
        addressee_id=user_b.id,
        status="declined",
    )
    db.add(friendship)
    await db.commit()
    friendship_id = str(friendship.id)

    # user_b re-requests user_a
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user_b.email, supabase_id=sid_b)):
        resp = await client.post("/api/v1/friends/request",
                                 json={"username": "user_a"},
                                 headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["friendship_id"] == friendship_id

    # Verify friendship is now pending with user_b as requester and user_a as addressee
    result = await db.execute(select(Friendship).where(Friendship.id == friendship.id))
    updated = result.scalar_one()
    assert updated.status == "pending"
    assert updated.requester_id == user_b.id
    assert updated.addressee_id == user_a.id


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
