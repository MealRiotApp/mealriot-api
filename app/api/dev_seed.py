"""
Dev-only seed endpoint for contest/social testing.
Creates fake users, friendships, a group, and daily points.
Only available when DEV_MODE=true.
"""
import uuid
import random
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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
