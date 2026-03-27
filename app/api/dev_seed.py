"""
Dev-only seed endpoint for contest/social testing.
Creates fake users, friendships, a group, and daily points.
Only available when DEV_MODE=true.
"""
import uuid
import random
from datetime import date, timedelta
from secrets import token_urlsafe
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, or_
from app.core.config import get_settings
from app.core.database import get_db
from app.api.deps import require_active_user
from app.models.models import (
    User, Friendship, CompetitionGroup, CompetitionMember, DailyPoints,
)

router = APIRouter(prefix="/api/v1/dev", tags=["dev"])

FAKE_USERS = [
    {"username": "test_alice", "name": "Alice Test", "email": "alice@test.dev"},
    {"username": "test_bob", "name": "Bob Test", "email": "bob@test.dev"},
    {"username": "test_charlie", "name": "Charlie Test", "email": "charlie@test.dev"},
]


# ---------------------------------------------------------------------------
# Task 4: Seed Scenario Helpers
# ---------------------------------------------------------------------------

def _fake_user_spec(index: int) -> dict:
    """Return user spec for fake user at 0-based index.

    First 3 reuse test_alice/bob/charlie, then test_user_4..test_user_20.
    """
    if index < len(FAKE_USERS):
        return FAKE_USERS[index]
    num = index + 1
    return {
        "username": f"test_user_{num}",
        "name": f"User {num} Test",
        "email": f"user{num}@test.dev",
    }


async def _ensure_fake_users(db: AsyncSession, count: int) -> list[User]:
    """Create or fetch *count* fake users. Idempotent."""
    users: list[User] = []
    for i in range(count):
        spec = _fake_user_spec(i)
        result = await db.execute(
            select(User).where(User.username == spec["username"])
        )
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                supabase_id=f"test-seed-{spec['username']}",
                email=spec["email"],
                name=spec["name"],
                username=spec["username"],
                status="active",
                friend_code=token_urlsafe(7)[:10],
            )
            db.add(user)
            await db.flush()
        users.append(user)
    return users


async def _cleanup_seed_data(db: AsyncSession, user_id) -> None:
    """Delete all seed-related data so scenarios start from a clean slate."""
    # Find all test user IDs
    result = await db.execute(
        select(User.id).where(User.username.like("test_%"))
    )
    test_user_ids = [row[0] for row in result.all()]
    all_ids = list(set(test_user_ids + [user_id]))

    # Delete DailyPoints for test users + current user
    await db.execute(
        delete(DailyPoints).where(DailyPoints.user_id.in_(all_ids))
    )

    # Delete CompetitionMembers for groups named "Test%"
    test_groups = await db.execute(
        select(CompetitionGroup.id).where(CompetitionGroup.name.like("Test%"))
    )
    test_group_ids = [row[0] for row in test_groups.all()]
    if test_group_ids:
        await db.execute(
            delete(CompetitionMember).where(
                CompetitionMember.group_id.in_(test_group_ids)
            )
        )
        # Delete the groups themselves
        await db.execute(
            delete(CompetitionGroup).where(
                CompetitionGroup.id.in_(test_group_ids)
            )
        )

    # Delete friendships involving test users
    if test_user_ids:
        await db.execute(
            delete(Friendship).where(
                or_(
                    Friendship.requester_id.in_(test_user_ids),
                    Friendship.addressee_id.in_(test_user_ids),
                )
            )
        )

    await db.flush()


async def _seed_points(
    db: AsyncSession,
    user_ids: list,
    pattern: str = "random",
) -> None:
    """Seed DailyPoints for current week (Monday to today).

    Patterns: random, high, low, zero.
    """
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday

    for uid in user_ids:
        for day_offset in range(7):
            d = week_start + timedelta(days=day_offset)
            if d > today:
                break
            # Check for existing row to avoid duplicates
            existing = await db.execute(
                select(DailyPoints).where(
                    DailyPoints.user_id == uid,
                    DailyPoints.date == d,
                )
            )
            if existing.scalar_one_or_none():
                continue

            if pattern == "zero":
                cal_pts = log_pts = macro_pts = 0
            elif pattern == "high":
                cal_pts = random.randint(8, 10)
                log_pts = random.randint(4, 5)
                macro_pts = random.randint(4, 5)
            elif pattern == "low":
                cal_pts = random.randint(0, 3)
                log_pts = random.randint(0, 1)
                macro_pts = random.randint(0, 1)
            else:  # random
                cal_pts = random.randint(0, 10)
                log_pts = random.randint(0, 5)
                macro_pts = random.randint(0, 5)

            db.add(DailyPoints(
                user_id=uid,
                date=d,
                calorie_points=cal_pts,
                logging_points=log_pts,
                macro_points=macro_pts,
                total_points=cal_pts + log_pts + macro_pts,
            ))

    await db.flush()


async def _create_friendships(
    db: AsyncSession,
    user_id,
    friends: list[User],
    status: str = "accepted",
) -> None:
    """Create friendships between user_id and each friend.

    For "accepted": requester=user_id.
    For "pending": requester=friend (incoming requests).
    """
    for friend in friends:
        if status == "pending":
            requester, addressee = friend.id, user_id
        else:
            requester, addressee = user_id, friend.id
        db.add(Friendship(
            requester_id=requester,
            addressee_id=addressee,
            status=status,
        ))
    await db.flush()


async def _create_group(
    db: AsyncSession,
    name: str,
    creator_id,
    member_ids: list,
) -> CompetitionGroup:
    """Create a CompetitionGroup and add all member_ids (including creator)."""
    group = CompetitionGroup(name=name, created_by=creator_id)
    db.add(group)
    await db.flush()
    for mid in member_ids:
        db.add(CompetitionMember(group_id=group.id, user_id=mid))
    await db.flush()
    return group


# ---------------------------------------------------------------------------
# Task 5: Scenario Registration + 14 Scenarios
# ---------------------------------------------------------------------------

SCENARIOS: dict[str, callable] = {}


def scenario(name: str):
    """Decorator to register a seed scenario function."""
    def decorator(fn):
        SCENARIOS[name] = fn
        return fn
    return decorator


async def _ensure_username(db: AsyncSession, user: User) -> None:
    """Ensure user has a username and friend_code."""
    if not user.username:
        user.username = "dev_user"
    if not user.friend_code:
        user.friend_code = token_urlsafe(7)[:10]
    await db.flush()


@scenario("no_username")
async def _scenario_no_username(db: AsyncSession, user: User) -> None:
    user.username = None
    await db.flush()


@scenario("no_friends_no_groups")
async def _scenario_no_friends_no_groups(db: AsyncSession, user: User) -> None:
    await _ensure_username(db, user)


@scenario("has_friends_no_groups")
async def _scenario_has_friends_no_groups(db: AsyncSession, user: User) -> None:
    await _ensure_username(db, user)
    friends = await _ensure_fake_users(db, 3)
    await _create_friendships(db, user.id, friends, "accepted")


@scenario("group_2_members")
async def _scenario_group_2_members(db: AsyncSession, user: User) -> None:
    await _ensure_username(db, user)
    friends = await _ensure_fake_users(db, 1)
    await _create_friendships(db, user.id, friends, "accepted")
    all_ids = [user.id] + [f.id for f in friends]
    await _create_group(db, "Test Duo", user.id, all_ids)
    await _seed_points(db, all_ids, "random")


@scenario("group_4_members")
async def _scenario_group_4_members(db: AsyncSession, user: User) -> None:
    await _ensure_username(db, user)
    friends = await _ensure_fake_users(db, 3)
    await _create_friendships(db, user.id, friends, "accepted")
    all_ids = [user.id] + [f.id for f in friends]
    await _create_group(db, "Test Squad", user.id, all_ids)
    await _seed_points(db, all_ids, "random")


@scenario("group_8_members")
async def _scenario_group_8_members(db: AsyncSession, user: User) -> None:
    await _ensure_username(db, user)
    friends = await _ensure_fake_users(db, 7)
    await _create_friendships(db, user.id, friends, "accepted")
    all_ids = [user.id] + [f.id for f in friends]
    await _create_group(db, "Test Octet", user.id, all_ids)
    await _seed_points(db, all_ids, "random")


@scenario("user_rank_1")
async def _scenario_user_rank_1(db: AsyncSession, user: User) -> None:
    await _ensure_username(db, user)
    friends = await _ensure_fake_users(db, 3)
    await _create_friendships(db, user.id, friends, "accepted")
    all_ids = [user.id] + [f.id for f in friends]
    await _create_group(db, "Test Rank1", user.id, all_ids)
    await _seed_points(db, [user.id], "high")
    await _seed_points(db, [f.id for f in friends], "low")


@scenario("user_last_place")
async def _scenario_user_last_place(db: AsyncSession, user: User) -> None:
    await _ensure_username(db, user)
    friends = await _ensure_fake_users(db, 3)
    await _create_friendships(db, user.id, friends, "accepted")
    all_ids = [user.id] + [f.id for f in friends]
    await _create_group(db, "Test Last", user.id, all_ids)
    await _seed_points(db, [user.id], "zero")
    await _seed_points(db, [f.id for f in friends], "high")


@scenario("all_tied_zero")
async def _scenario_all_tied_zero(db: AsyncSession, user: User) -> None:
    await _ensure_username(db, user)
    friends = await _ensure_fake_users(db, 3)
    await _create_friendships(db, user.id, friends, "accepted")
    all_ids = [user.id] + [f.id for f in friends]
    await _create_group(db, "Test Tied", user.id, all_ids)
    # No points seeded — all tied at zero


@scenario("pending_requests")
async def _scenario_pending_requests(db: AsyncSession, user: User) -> None:
    await _ensure_username(db, user)
    friends = await _ensure_fake_users(db, 3)
    await _create_friendships(db, user.id, friends, "pending")


@scenario("max_friends")
async def _scenario_max_friends(db: AsyncSession, user: User) -> None:
    await _ensure_username(db, user)
    friends = await _ensure_fake_users(db, 20)
    await _create_friendships(db, user.id, friends, "accepted")


@scenario("has_friends_no_pending")
async def _scenario_has_friends_no_pending(db: AsyncSession, user: User) -> None:
    await _ensure_username(db, user)
    friends = await _ensure_fake_users(db, 5)
    await _create_friendships(db, user.id, friends, "accepted")


@scenario("two_groups_max")
async def _scenario_two_groups_max(db: AsyncSession, user: User) -> None:
    await _ensure_username(db, user)
    friends = await _ensure_fake_users(db, 3)
    await _create_friendships(db, user.id, friends, "accepted")
    # Group 1: user + friends[0] + friends[1]
    g1_ids = [user.id, friends[0].id, friends[1].id]
    await _create_group(db, "Test Alpha", user.id, g1_ids)
    # Group 2: user + friends[1] + friends[2] (friends[1] overlaps)
    g2_ids = [user.id, friends[1].id, friends[2].id]
    await _create_group(db, "Test Beta", user.id, g2_ids)
    await _seed_points(db, [user.id] + [f.id for f in friends], "random")


@scenario("long_usernames")
async def _scenario_long_usernames(db: AsyncSession, user: User) -> None:
    await _ensure_username(db, user)
    # Create 3 users with 30-char usernames
    long_users: list[User] = []
    for i in range(3):
        uname = f"test_long_username_{i:011d}"  # exactly 30 chars
        result = await db.execute(
            select(User).where(User.username == uname)
        )
        u = result.scalar_one_or_none()
        if not u:
            u = User(
                supabase_id=f"test-seed-{uname}",
                email=f"long{i}@test.dev",
                name=f"Long Name User {i}",
                username=uname,
                status="active",
                friend_code=token_urlsafe(7)[:10],
            )
            db.add(u)
            await db.flush()
        long_users.append(u)
    await _create_friendships(db, user.id, long_users, "accepted")
    all_ids = [user.id] + [u.id for u in long_users]
    await _create_group(db, "Test LongNames", user.id, all_ids)
    await _seed_points(db, all_ids, "random")


# ---------------------------------------------------------------------------
# Pydantic body for seed-scenario endpoint
# ---------------------------------------------------------------------------

class SeedScenarioBody(BaseModel):
    scenario: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/seed-contest")
async def seed_contest(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    settings = get_settings()
    if not getattr(settings, "dev_mode", False):
        raise HTTPException(403, detail="Seed disabled in production")

    created_users: list[User] = []

    # 1. Create or fetch fake users (idempotent)
    for fake in FAKE_USERS:
        result = await db.execute(
            select(User).where(User.username == fake["username"])
        )
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                supabase_id=f"dev-seed-{fake['username']}-{uuid.uuid4()}",
                email=fake["email"],
                name=fake["name"],
                username=fake["username"],
                status="active",
                friend_code=uuid.uuid4().hex[:10],
            )
            db.add(user)
            await db.flush()
        created_users.append(user)

    # 2. Create friendships with current user (idempotent)
    for user in created_users:
        existing = await db.execute(
            select(Friendship).where(
                ((Friendship.requester_id == current_user.id) & (Friendship.addressee_id == user.id))
                | ((Friendship.requester_id == user.id) & (Friendship.addressee_id == current_user.id))
            )
        )
        if not existing.scalar_one_or_none():
            db.add(Friendship(
                requester_id=current_user.id,
                addressee_id=user.id,
                status="accepted",
            ))

    # 3. Create group "Test Squad" (idempotent)
    result = await db.execute(
        select(CompetitionGroup).where(
            CompetitionGroup.name == "Test Squad",
            CompetitionGroup.created_by == current_user.id,
        )
    )
    group = result.scalar_one_or_none()
    if not group:
        group = CompetitionGroup(name="Test Squad", created_by=current_user.id)
        db.add(group)
        await db.flush()

    # Add all users + current user as members (idempotent)
    all_users = [current_user] + created_users
    for user in all_users:
        existing = await db.execute(
            select(CompetitionMember).where(
                CompetitionMember.group_id == group.id,
                CompetitionMember.user_id == user.id,
            )
        )
        if not existing.scalar_one_or_none():
            db.add(CompetitionMember(group_id=group.id, user_id=user.id))

    # 4. Populate daily points for current week
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday
    for user in all_users:
        for day_offset in range(7):
            d = week_start + timedelta(days=day_offset)
            if d > today:
                break
            existing = await db.execute(
                select(DailyPoints).where(
                    DailyPoints.user_id == user.id,
                    DailyPoints.date == d,
                )
            )
            if not existing.scalar_one_or_none():
                cal_pts = random.randint(0, 10)
                log_pts = random.randint(0, 5)
                macro_pts = random.randint(0, 5)
                db.add(DailyPoints(
                    user_id=user.id,
                    date=d,
                    calorie_points=cal_pts,
                    logging_points=log_pts,
                    macro_points=macro_pts,
                    total_points=cal_pts + log_pts + macro_pts,
                ))

    await db.commit()

    return {
        "status": "seeded",
        "users": [u.username for u in created_users],
        "group": group.name,
        "group_id": str(group.id),
    }


@router.post("/seed-scenario")
async def seed_scenario(
    body: SeedScenarioBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    settings = get_settings()
    if not getattr(settings, "dev_mode", False):
        raise HTTPException(403, detail="Seed disabled in production")

    if body.scenario not in SCENARIOS:
        raise HTTPException(
            400,
            detail=f"Unknown scenario '{body.scenario}'. "
                   f"Available: {sorted(SCENARIOS.keys())}",
        )

    await _cleanup_seed_data(db, current_user.id)
    await SCENARIOS[body.scenario](db, current_user)
    await db.commit()

    return {"ok": True, "scenario": body.scenario}
