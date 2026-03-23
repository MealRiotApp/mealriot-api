import uuid as uuid_mod
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from app.api.deps import require_active_user
from app.core.database import get_db
from app.models.models import (
    User, Friendship, CompetitionGroup, CompetitionMember,
    DailyPoints, WeeklySummary, FoodEntry,
)
from app.schemas.social import (
    GroupCreateBody, GroupOut, LeaderboardResponse, StandingOut, HistoryResponse, WeekHistoryItem,
)

router = APIRouter(prefix="/api/v1/groups", tags=["groups"])


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


@router.post("", status_code=201)
async def create_group(
    body: GroupCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    if len(body.member_ids) > 7:
        raise HTTPException(400, detail={"error": {"code": "GROUP_TOO_LARGE", "message": "Max 8 members"}})

    # Check max 2 competitions
    count = await db.execute(
        select(func.count()).select_from(CompetitionMember).where(
            CompetitionMember.user_id == current_user.id,
        )
    )
    if count.scalar() >= 2:
        raise HTTPException(400, detail={"error": {"code": "MAX_COMPETITIONS_REACHED", "message": "Max 2 active competitions"}})

    # Verify all members are friends
    for mid in body.member_ids:
        uid = uuid_mod.UUID(mid)
        friend_check = await db.execute(
            select(Friendship).where(
                Friendship.status == "accepted",
                or_(
                    and_(Friendship.requester_id == current_user.id, Friendship.addressee_id == uid),
                    and_(Friendship.requester_id == uid, Friendship.addressee_id == current_user.id),
                ),
            )
        )
        if not friend_check.scalar_one_or_none():
            raise HTTPException(400, detail={"error": {"code": "INVALID_MEMBER", "message": f"User {mid} is not a friend"}})

    group = CompetitionGroup(name=body.name, created_by=current_user.id)
    db.add(group)
    await db.flush()

    # Add creator + members
    db.add(CompetitionMember(group_id=group.id, user_id=current_user.id))
    for mid in body.member_ids:
        db.add(CompetitionMember(group_id=group.id, user_id=uuid_mod.UUID(mid)))
    await db.commit()
    return {"group_id": str(group.id), "name": group.name, "members": [str(current_user.id)] + body.member_ids}


@router.get("", response_model=list[GroupOut])
async def list_groups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    stmt = (
        select(CompetitionGroup, func.count(CompetitionMember.id).label("cnt"))
        .join(CompetitionMember, CompetitionMember.group_id == CompetitionGroup.id)
        .where(
            CompetitionGroup.id.in_(
                select(CompetitionMember.group_id).where(CompetitionMember.user_id == current_user.id)
            ),
            CompetitionGroup.is_active == True,
        )
        .group_by(CompetitionGroup.id)
    )
    result = await db.execute(stmt)
    groups = []
    for row in result.all():
        g = row[0]
        groups.append(GroupOut(group_id=str(g.id), name=g.name, member_count=row[1]))
    return groups


@router.get("/{group_id}/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    gid = uuid_mod.UUID(group_id)
    # Verify membership
    member = await db.execute(
        select(CompetitionMember).where(
            CompetitionMember.group_id == gid,
            CompetitionMember.user_id == current_user.id,
        )
    )
    if not member.scalar_one_or_none():
        raise HTTPException(403, detail="Not a member of this group")

    today = date.today()
    ws = _week_start(today)
    days_in_week = (today - ws).days + 1

    # Get all members
    members_result = await db.execute(
        select(CompetitionMember).where(CompetitionMember.group_id == gid)
    )
    members = members_result.scalars().all()

    standings = []
    for m in members:
        pts_result = await db.execute(
            select(func.coalesce(func.sum(DailyPoints.total_points), 0)).where(
                DailyPoints.user_id == m.user_id,
                DailyPoints.date >= ws,
                DailyPoints.date <= today,
            )
        )
        total_pts = pts_result.scalar()
        # Days logged
        days_result = await db.execute(
            select(func.count(func.distinct(func.date(FoodEntry.logged_at)))).where(
                FoodEntry.user_id == m.user_id,
                func.date(FoodEntry.logged_at) >= ws,
                func.date(FoodEntry.logged_at) <= today,
            )
        )
        days_logged = days_result.scalar()
        user = await db.get(User, m.user_id)
        standings.append({
            "user_id": str(m.user_id),
            "name": user.name if user else "Unknown",
            "total_points": total_pts,
            "days_logged": days_logged,
            "days_in_week": days_in_week,
            "is_current_user": m.user_id == current_user.id,
        })

    standings.sort(key=lambda x: (-x["total_points"], -x["days_logged"]))
    for i, s in enumerate(standings):
        s["rank"] = i + 1

    return LeaderboardResponse(
        week_start=ws.isoformat(),
        standings=[StandingOut(**s) for s in standings],
    )


@router.get("/{group_id}/history", response_model=HistoryResponse)
async def get_history(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    gid = uuid_mod.UUID(group_id)
    result = await db.execute(
        select(WeeklySummary)
        .where(WeeklySummary.group_id == gid)
        .order_by(WeeklySummary.week_start.desc())
        .limit(84)  # 12 weeks * max 7 members
    )
    summaries = result.scalars().all()
    weeks_map: dict[str, list] = {}
    for s in summaries:
        ws = s.week_start.isoformat()
        if ws not in weeks_map:
            weeks_map[ws] = []
        user = await db.get(User, s.user_id)
        weeks_map[ws].append(StandingOut(
            rank=s.rank or 0,
            user_id=str(s.user_id),
            name=user.name if user else "Unknown",
            total_points=s.total_points,
            days_logged=0,
            days_in_week=7,
            is_current_user=s.user_id == current_user.id,
        ))
    weeks = [WeekHistoryItem(week_start=ws, standings=st) for ws, st in weeks_map.items()]
    return HistoryResponse(weeks=weeks[:12])


@router.delete("/{group_id}/members/me", status_code=204)
async def leave_group(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    gid = uuid_mod.UUID(group_id)
    result = await db.execute(
        select(CompetitionMember).where(
            CompetitionMember.group_id == gid,
            CompetitionMember.user_id == current_user.id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(404, detail="Not a member")
    await db.delete(member)
    await db.commit()
