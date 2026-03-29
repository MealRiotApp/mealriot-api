import secrets
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, func
from app.api.deps import require_active_user
from app.core.database import get_db
from app.models.models import User, Friendship, DailyPoints
from app.schemas.social import (
    FriendOut, FriendRequestOut, FriendRequestBody,
    FriendActionBody, UsernameSetBody,
    LeaderboardResponse, StandingOut,
)
from app.middleware.rate_limit import limiter

router = APIRouter(prefix="/api/v1/friends", tags=["friends"])


@router.get("", response_model=list[FriendOut])
@limiter.limit("60/minute")
async def list_friends(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    stmt = select(Friendship).where(
        Friendship.status == "accepted",
        or_(
            Friendship.requester_id == current_user.id,
            Friendship.addressee_id == current_user.id,
        ),
    )
    result = await db.execute(stmt)
    friendships = result.scalars().all()
    friends = []
    for f in friendships:
        friend_id = f.addressee_id if f.requester_id == current_user.id else f.requester_id
        u = await db.get(User, friend_id)
        if u:
            friends.append(FriendOut(
                user_id=str(u.id),
                username=u.username,
                name=u.name,
                avatar_url=u.avatar_url,
                created_at=f.created_at.isoformat() if f.created_at else None,
            ))
    # Sort by created_at desc (newest friendships first)
    friends.sort(key=lambda x: x.created_at or "", reverse=True)
    return friends


@router.post("/request", status_code=201)
@limiter.limit("60/minute")
async def send_request(
    request: Request,
    body: FriendRequestBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    if not current_user.username:
        raise HTTPException(400, detail="Set a username before sending friend requests")

    result = await db.execute(select(User).where(User.username == body.username))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(404, detail={"error": {"code": "USER_NOT_FOUND", "message": "User not found"}})

    if target.id == current_user.id:
        raise HTTPException(400, detail={"error": {"code": "CANNOT_FRIEND_SELF", "message": "Cannot send friend request to yourself"}})

    # Check existing
    existing = await db.execute(
        select(Friendship).where(
            or_(
                and_(Friendship.requester_id == current_user.id, Friendship.addressee_id == target.id),
                and_(Friendship.requester_id == target.id, Friendship.addressee_id == current_user.id),
            )
        )
    )
    ex = existing.scalar_one_or_none()
    if ex:
        if ex.status == "accepted":
            raise HTTPException(409, detail={"error": {"code": "ALREADY_FRIENDS", "message": "Already friends"}})
        elif ex.status == "blocked":
            raise HTTPException(422, detail={"error": {"code": "BLOCKED", "message": "Blocked"}})
        elif ex.status == "pending":
            raise HTTPException(409, detail={"error": {"code": "REQUEST_ALREADY_SENT", "message": "Request already sent"}})
        elif ex.status == "declined":
            # Check max friends limit
            count = await db.execute(
                select(func.count()).select_from(Friendship).where(
                    Friendship.status == "accepted",
                    or_(Friendship.requester_id == current_user.id, Friendship.addressee_id == current_user.id),
                )
            )
            if count.scalar() >= 20:
                raise HTTPException(400, detail={"error": {"code": "MAX_FRIENDS_REACHED", "message": "Max 20 friends"}})
            ex.status = "pending"
            ex.requester_id = current_user.id
            ex.addressee_id = target.id
            await db.commit()
            return {"friendship_id": str(ex.id)}

    # Count friends limit
    count = await db.execute(
        select(func.count()).select_from(Friendship).where(
            Friendship.status == "accepted",
            or_(Friendship.requester_id == current_user.id, Friendship.addressee_id == current_user.id),
        )
    )
    if count.scalar() >= 20:
        raise HTTPException(400, detail={"error": {"code": "MAX_FRIENDS_REACHED", "message": "Max 20 friends"}})

    friendship = Friendship(requester_id=current_user.id, addressee_id=target.id)
    db.add(friendship)
    await db.commit()
    return {"friendship_id": str(friendship.id)}


@router.get("/requests", response_model=list[FriendRequestOut])
@limiter.limit("60/minute")
async def get_requests(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    result = await db.execute(
        select(Friendship).where(
            Friendship.addressee_id == current_user.id,
            Friendship.status == "pending",
        )
    )
    requests = []
    for f in result.scalars().all():
        u = await db.get(User, f.requester_id)
        if u:
            requests.append(FriendRequestOut(
                friendship_id=str(f.id),
                requester=FriendOut(user_id=str(u.id), username=u.username, name=u.name),
                created_at=f.created_at.isoformat() if f.created_at else "",
            ))
    return requests


@router.get("/resolve")
@limiter.limit("60/minute")
async def resolve_friend_code(
    request: Request,
    code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    result = await db.execute(select(User).where(User.friend_code == code))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, detail={"error": {"code": "FRIEND_CODE_NOT_FOUND", "message": "Friend code not found"}})
    return {"username": user.username, "name": user.name}


@router.get("/leaderboard", response_model=LeaderboardResponse)
@limiter.limit("60/minute")
async def friends_leaderboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_end = week_start + timedelta(days=6)
    days_in_week = min((today - week_start).days + 1, 7)

    # Get accepted friend user IDs
    stmt = select(Friendship).where(
        Friendship.status == "accepted",
        or_(
            Friendship.requester_id == current_user.id,
            Friendship.addressee_id == current_user.id,
        ),
    )
    result = await db.execute(stmt)
    friendships = result.scalars().all()

    friend_ids = set()
    for f in friendships:
        friend_ids.add(f.addressee_id if f.requester_id == current_user.id else f.requester_id)

    all_user_ids = list(friend_ids | {current_user.id})

    # For each user, sum points and count days logged
    standings_data = []
    for uid in all_user_ids:
        # Sum total_points for the week
        pts_result = await db.execute(
            select(func.coalesce(func.sum(DailyPoints.total_points), 0)).where(
                DailyPoints.user_id == uid,
                DailyPoints.date >= week_start,
                DailyPoints.date <= week_end,
            )
        )
        total_points = pts_result.scalar()

        # Count distinct days with total_points > 0
        days_result = await db.execute(
            select(func.count(func.distinct(DailyPoints.date))).where(
                DailyPoints.user_id == uid,
                DailyPoints.date >= week_start,
                DailyPoints.date <= week_end,
                DailyPoints.total_points > 0,
            )
        )
        days_logged = days_result.scalar()

        user = await db.get(User, uid)
        standings_data.append({
            "user_id": str(uid),
            "name": user.name if user else "Unknown",
            "username": user.username if user else None,
            "total_points": total_points,
            "days_logged": days_logged,
            "is_current_user": uid == current_user.id,
        })

    # Sort by (-total_points, -days_logged)
    standings_data.sort(key=lambda x: (-x["total_points"], -x["days_logged"]))

    # Assign ranks
    standings = []
    for i, s in enumerate(standings_data):
        standings.append(StandingOut(
            rank=i + 1,
            user_id=s["user_id"],
            name=s["name"],
            username=s["username"],
            total_points=s["total_points"],
            days_logged=s["days_logged"],
            days_in_week=days_in_week,
            is_current_user=s["is_current_user"],
        ))

    return LeaderboardResponse(
        week_start=week_start.isoformat(),
        standings=standings,
    )


@router.patch("/{friendship_id}")
@limiter.limit("60/minute")
async def respond_to_request(
    request: Request,
    friendship_id: str,
    body: FriendActionBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    import uuid as uuid_mod
    result = await db.execute(
        select(Friendship).where(Friendship.id == uuid_mod.UUID(friendship_id))
    )
    f = result.scalar_one_or_none()
    if not f or f.addressee_id != current_user.id:
        raise HTTPException(404, detail="Request not found")
    if body.action == "accept":
        f.status = "accepted"
    elif body.action == "decline":
        f.status = "declined"
    elif body.action == "block":
        f.status = "blocked"
    else:
        raise HTTPException(400, detail="Invalid action")
    await db.commit()
    return {"status": f.status}


@router.get("/suggest")
async def suggest_users(
    q: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    if len(q) < 2:
        return {"results": []}
    blocked_ids = select(Friendship.requester_id).where(
        Friendship.addressee_id == current_user.id,
        Friendship.status == "blocked",
    ).union(
        select(Friendship.addressee_id).where(
            Friendship.requester_id == current_user.id,
            Friendship.status == "blocked",
        )
    )
    result = await db.execute(
        select(User.username)
        .where(
            User.username.isnot(None),
            User.username.ilike(f"{q}%"),
            User.id != current_user.id,
            User.id.notin_(blocked_ids),
        )
        .limit(10)
    )
    return {"results": [r[0] for r in result.all() if r[0]]}


@router.get("/search")
@limiter.limit("60/minute")
async def search_user(
    request: Request,
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        return {"result": None}
    if user.id == current_user.id:
        return {"result": None}
    # Check if blocked
    blocked = await db.execute(
        select(Friendship).where(
            or_(
                and_(Friendship.requester_id == user.id, Friendship.addressee_id == current_user.id, Friendship.status == "blocked"),
                and_(Friendship.requester_id == current_user.id, Friendship.addressee_id == user.id, Friendship.status == "blocked"),
            )
        )
    )
    if blocked.scalar_one_or_none():
        return {"result": None}
    return {"result": {"user_id": str(user.id), "username": user.username, "name": user.name}}


@router.post("/username")
@limiter.limit("60/minute")
async def set_username(
    request: Request,
    body: UsernameSetBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(409, detail={"error": {"code": "USERNAME_TAKEN", "message": "Username taken"}})
    current_user.username = body.username
    if not current_user.friend_code:
        current_user.friend_code = secrets.token_urlsafe(7)[:10]
    await db.commit()
    return {"username": current_user.username, "friend_code": current_user.friend_code}
