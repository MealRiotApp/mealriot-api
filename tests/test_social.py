import uuid
import pytest
from unittest.mock import patch
from tests.conftest import make_jwt_payload, make_active_user


async def test_set_username(client, db):
    user, sid = await make_active_user(db)
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.post("/api/v1/friends/username",
                                 json={"username": "testuser"},
                                 headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "testuser"
    assert resp.json()["friend_code"]


async def test_set_username_taken(client, db):
    user1, sid1 = await make_active_user(db, email="u1@test.com")
    user2, sid2 = await make_active_user(db, email="u2@test.com")
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user1.email, supabase_id=sid1)):
        await client.post("/api/v1/friends/username",
                          json={"username": "taken"},
                          headers={"Authorization": "Bearer faketoken"})
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user2.email, supabase_id=sid2)):
        resp = await client.post("/api/v1/friends/username",
                                 json={"username": "taken"},
                                 headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 409


async def test_search_user(client, db):
    user, sid = await make_active_user(db)
    user.username = "searchable"
    await db.commit()
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.get("/api/v1/friends/search?username=searchable",
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    assert resp.json()["result"]["username"] == "searchable"


async def test_search_nonexistent(client, db):
    user, sid = await make_active_user(db)
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.get("/api/v1/friends/search?username=nobody",
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.json()["result"] is None


async def test_friend_request_flow(client, db):
    user1, sid1 = await make_active_user(db, email="a@test.com")
    user2, sid2 = await make_active_user(db, email="b@test.com")
    user1.username = "user_a"
    user2.username = "user_b"
    await db.commit()

    # Send request
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user1.email, supabase_id=sid1)):
        resp = await client.post("/api/v1/friends/request",
                                 json={"username": "user_b"},
                                 headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 201
    fid = resp.json()["friendship_id"]

    # Get pending requests
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user2.email, supabase_id=sid2)):
        resp = await client.get("/api/v1/friends/requests",
                                headers={"Authorization": "Bearer faketoken"})
    assert len(resp.json()) == 1

    # Accept
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user2.email, supabase_id=sid2)):
        resp = await client.patch(f"/api/v1/friends/{fid}",
                                  json={"action": "accept"},
                                  headers={"Authorization": "Bearer faketoken"})
    assert resp.json()["status"] == "accepted"

    # List friends
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user1.email, supabase_id=sid1)):
        resp = await client.get("/api/v1/friends",
                                headers={"Authorization": "Bearer faketoken"})
    assert len(resp.json()) == 1


async def test_list_groups_empty(client, db):
    user, sid = await make_active_user(db)
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.get("/api/v1/groups",
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_points_today(client, db):
    user, sid = await make_active_user(db)
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.get("/api/v1/points/today",
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    assert resp.json()["total_points"] == 0


async def test_points_week(client, db):
    user, sid = await make_active_user(db)
    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.get("/api/v1/points/week",
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    assert resp.json()["total_points"] == 0


async def test_list_friends_includes_avatar_and_created_at(client, db):
    from app.models.models import User, Friendship
    user1, sid1 = await make_active_user(db, email="user1@test.com")
    user2 = User(
        supabase_id=str(uuid.uuid4()), email="user2@test.com", name="Friend",
        role="member", status="active", avatar_url="https://example.com/avatar.jpg",
    )
    db.add(user2)
    await db.commit()
    await db.refresh(user2)

    friendship = Friendship(requester_id=user1.id, addressee_id=user2.id, status="accepted")
    db.add(friendship)
    await db.commit()

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user1.email, supabase_id=sid1)):
        resp = await client.get("/api/v1/friends",
                                headers={"Authorization": "Bearer faketoken"})

    assert resp.status_code == 200
    friends = resp.json()
    assert len(friends) == 1
    assert friends[0]["avatar_url"] == "https://example.com/avatar.jpg"
    assert friends[0]["created_at"] is not None
