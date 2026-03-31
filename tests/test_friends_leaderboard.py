import uuid
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from app.models.models import User, Friendship, DailyPoints
from tests.conftest import make_jwt_payload, make_active_user


def _week_start(first_day_of_week: int = 0) -> date:
    """Calculate week start respecting first_day_of_week (0=Sunday, 1=Monday)."""
    today = date.today()
    py_fdow = 6 if first_day_of_week == 0 else first_day_of_week - 1
    days_since_start = (today.weekday() - py_fdow) % 7
    return today - timedelta(days=days_since_start)


async def _add_points(db, user_id, total_points: int, day_offset: int = 0):
    ws = _week_start()
    dp = DailyPoints(
        user_id=user_id,
        date=ws + timedelta(days=day_offset),
        calorie_points=total_points,
        logging_points=0,
        macro_points=0,
        total_points=total_points,
    )
    db.add(dp)
    await db.flush()


async def test_leaderboard_no_friends(client, db):
    user, sid = await make_active_user(db, "solo@test.com")
    user.username = "solo_user"
    await db.commit()

    payload = make_jwt_payload("solo@test.com", sid)
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.get("/api/v1/friends/leaderboard", headers={"Authorization": "Bearer fake"})

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["standings"]) == 1
    assert data["standings"][0]["total_points"] == 0
    assert data["standings"][0]["is_current_user"] is True


async def test_leaderboard_with_friends_and_points(client, db):
    user, sid = await make_active_user(db, "me@test.com")
    user.username = "me_user"
    await db.flush()

    # Create 2 friends
    friend1 = User(
        supabase_id=str(uuid.uuid4()), email="f1@test.com",
        name="Friend One", username="friend1", status="active",
    )
    friend2 = User(
        supabase_id=str(uuid.uuid4()), email="f2@test.com",
        name="Friend Two", username="friend2", status="active",
    )
    db.add_all([friend1, friend2])
    await db.flush()

    # Create accepted friendships
    db.add(Friendship(requester_id=user.id, addressee_id=friend1.id, status="accepted"))
    db.add(Friendship(requester_id=friend2.id, addressee_id=user.id, status="accepted"))
    await db.flush()

    # Seed points: friend1=30, user=20, friend2=10
    await _add_points(db, friend1.id, 20, day_offset=0)
    await _add_points(db, friend1.id, 10, day_offset=1)
    await _add_points(db, user.id, 20, day_offset=0)
    await _add_points(db, friend2.id, 10, day_offset=0)
    await db.commit()

    payload = make_jwt_payload("me@test.com", sid)
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.get("/api/v1/friends/leaderboard", headers={"Authorization": "Bearer fake"})

    assert resp.status_code == 200
    data = resp.json()
    standings = data["standings"]
    assert len(standings) == 3

    # Verify order: highest first
    assert standings[0]["total_points"] == 30
    assert standings[0]["rank"] == 1
    assert standings[1]["total_points"] == 20
    assert standings[1]["rank"] == 2
    assert standings[2]["total_points"] == 10
    assert standings[2]["rank"] == 3

    # Verify is_current_user flag
    current_users = [s for s in standings if s["is_current_user"]]
    assert len(current_users) == 1
    assert current_users[0]["total_points"] == 20


async def test_leaderboard_excludes_non_accepted(client, db):
    user, sid = await make_active_user(db, "main@test.com")
    user.username = "main_user"
    await db.flush()

    pending_friend = User(
        supabase_id=str(uuid.uuid4()), email="pending@test.com",
        name="Pending Friend", username="pending_f", status="active",
    )
    blocked_friend = User(
        supabase_id=str(uuid.uuid4()), email="blocked@test.com",
        name="Blocked Friend", username="blocked_f", status="active",
    )
    accepted_friend = User(
        supabase_id=str(uuid.uuid4()), email="accepted@test.com",
        name="Accepted Friend", username="accepted_f", status="active",
    )
    db.add_all([pending_friend, blocked_friend, accepted_friend])
    await db.flush()

    db.add(Friendship(requester_id=user.id, addressee_id=pending_friend.id, status="pending"))
    db.add(Friendship(requester_id=user.id, addressee_id=blocked_friend.id, status="blocked"))
    db.add(Friendship(requester_id=user.id, addressee_id=accepted_friend.id, status="accepted"))
    await db.commit()

    payload = make_jwt_payload("main@test.com", sid)
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.get("/api/v1/friends/leaderboard", headers={"Authorization": "Bearer fake"})

    assert resp.status_code == 200
    data = resp.json()
    # Only user + accepted friend
    assert len(data["standings"]) == 2
    user_ids = {s["user_id"] for s in data["standings"]}
    assert str(pending_friend.id) not in user_ids
    assert str(blocked_friend.id) not in user_ids


async def test_leaderboard_has_week_start(client, db):
    user, sid = await make_active_user(db, "weektest@test.com")
    user.username = "week_user"
    await db.commit()

    payload = make_jwt_payload("weektest@test.com", sid)
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.get("/api/v1/friends/leaderboard", headers={"Authorization": "Bearer fake"})

    assert resp.status_code == 200
    data = resp.json()
    week_start = date.fromisoformat(data["week_start"])
    assert week_start.weekday() == 6  # Sunday (default first_day_of_week=0)


async def test_leaderboard_tied_ranks(client, db):
    """Users with the same total_points should share the same rank."""
    user, sid = await make_active_user(db, "tie_me@test.com")
    user.username = "tie_user"
    await db.flush()

    friends = []
    for i in range(3):
        f = User(
            supabase_id=str(uuid.uuid4()), email=f"tie_f{i}@test.com",
            name=f"Tie Friend {i}", username=f"tie_friend_{i}", status="active",
        )
        db.add(f)
        friends.append(f)
    await db.flush()

    for f in friends:
        db.add(Friendship(requester_id=user.id, addressee_id=f.id, status="accepted"))
    await db.flush()

    await _add_points(db, user.id, 30, day_offset=0)
    await _add_points(db, friends[0].id, 30, day_offset=0)
    await _add_points(db, friends[1].id, 20, day_offset=0)
    await _add_points(db, friends[2].id, 20, day_offset=0)
    await db.commit()

    payload = make_jwt_payload("tie_me@test.com", sid)
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.get("/api/v1/friends/leaderboard", headers={"Authorization": "Bearer fake"})

    assert resp.status_code == 200
    standings = resp.json()["standings"]
    assert len(standings) == 4

    ranks_30 = [s["rank"] for s in standings if s["total_points"] == 30]
    assert ranks_30 == [1, 1]

    ranks_20 = [s["rank"] for s in standings if s["total_points"] == 20]
    assert ranks_20 == [2, 2]
