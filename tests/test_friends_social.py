from unittest.mock import patch
from tests.conftest import make_jwt_payload, make_active_user
from app.models.models import Friendship
from sqlalchemy import select


async def test_sent_requests_returns_only_requester_pending(client, db):
    user_a, sid_a = await make_active_user(db, email="a@test.com")
    user_a.username = "user_a"
    user_b, sid_b = await make_active_user(db, email="b@test.com")
    user_b.username = "user_b"
    await db.commit()

    friendship = Friendship(requester_id=user_a.id, addressee_id=user_b.id, status="pending")
    db.add(friendship)
    await db.commit()

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user_a.email, supabase_id=sid_a)):
        resp = await client.get("/api/v1/friends/requests/sent",
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["addressee"]["username"] == "user_b"
    assert data[0]["friendship_id"] == str(friendship.id)

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user_b.email, supabase_id=sid_b)):
        resp = await client.get("/api/v1/friends/requests/sent",
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    assert len(resp.json()) == 0


async def test_sent_requests_excludes_accepted(client, db):
    user_a, sid_a = await make_active_user(db, email="a@test.com")
    user_a.username = "user_a"
    user_b, sid_b = await make_active_user(db, email="b@test.com")
    user_b.username = "user_b"
    await db.commit()

    friendship = Friendship(requester_id=user_a.id, addressee_id=user_b.id, status="accepted")
    db.add(friendship)
    await db.commit()

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user_a.email, supabase_id=sid_a)):
        resp = await client.get("/api/v1/friends/requests/sent",
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    assert len(resp.json()) == 0


async def test_cancel_request_success(client, db):
    user_a, sid_a = await make_active_user(db, email="a@test.com")
    user_a.username = "user_a"
    user_b, sid_b = await make_active_user(db, email="b@test.com")
    user_b.username = "user_b"
    await db.commit()

    friendship = Friendship(requester_id=user_a.id, addressee_id=user_b.id, status="pending")
    db.add(friendship)
    await db.commit()
    fid = str(friendship.id)

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user_a.email, supabase_id=sid_a)):
        resp = await client.delete(f"/api/v1/friends/requests/{fid}",
                                   headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 204

    result = await db.execute(select(Friendship).where(Friendship.id == friendship.id))
    assert result.scalar_one_or_none() is None


async def test_cancel_request_wrong_user(client, db):
    user_a, sid_a = await make_active_user(db, email="a@test.com")
    user_a.username = "user_a"
    user_b, sid_b = await make_active_user(db, email="b@test.com")
    user_b.username = "user_b"
    await db.commit()

    friendship = Friendship(requester_id=user_a.id, addressee_id=user_b.id, status="pending")
    db.add(friendship)
    await db.commit()
    fid = str(friendship.id)

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user_b.email, supabase_id=sid_b)):
        resp = await client.delete(f"/api/v1/friends/requests/{fid}",
                                   headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 403


async def test_cancel_request_not_pending(client, db):
    user_a, sid_a = await make_active_user(db, email="a@test.com")
    user_a.username = "user_a"
    user_b, sid_b = await make_active_user(db, email="b@test.com")
    user_b.username = "user_b"
    await db.commit()

    friendship = Friendship(requester_id=user_a.id, addressee_id=user_b.id, status="accepted")
    db.add(friendship)
    await db.commit()
    fid = str(friendship.id)

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user_a.email, supabase_id=sid_a)):
        resp = await client.delete(f"/api/v1/friends/requests/{fid}",
                                   headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 404


async def test_friend_profile_success(client, db):
    user_a, sid_a = await make_active_user(db, email="a@test.com")
    user_a.username = "user_a"
    user_a.longest_streak = 42
    user_b, sid_b = await make_active_user(db, email="b@test.com")
    user_b.username = "user_b"
    user_b.longest_streak = 10
    await db.commit()

    friendship = Friendship(requester_id=user_a.id, addressee_id=user_b.id, status="accepted")
    db.add(friendship)
    await db.commit()

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user_a.email, supabase_id=sid_a)):
        resp = await client.get(f"/api/v1/friends/{user_b.id}/profile",
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test User"
    assert data["username"] == "user_b"
    assert data["longest_streak"] == 10
    assert "joined" in data
    assert "friends_since" in data


async def test_friend_profile_not_friends(client, db):
    user_a, sid_a = await make_active_user(db, email="a@test.com")
    user_b, sid_b = await make_active_user(db, email="b@test.com")
    await db.commit()

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user_a.email, supabase_id=sid_a)):
        resp = await client.get(f"/api/v1/friends/{user_b.id}/profile",
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 403


async def test_leaderboard_includes_avatar_url(client, db):
    user_a, sid_a = await make_active_user(db, email="a@test.com")
    user_a.username = "user_a"
    user_a.avatar_url = "https://example.com/avatar.jpg"
    await db.commit()

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user_a.email, supabase_id=sid_a)):
        resp = await client.get("/api/v1/friends/leaderboard",
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    standings = resp.json()["standings"]
    assert len(standings) == 1
    assert standings[0]["avatar_url"] == "https://example.com/avatar.jpg"
