import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, func
from app.api.deps import require_active_user
from app.core.database import get_db
from app.models.models import User, Friendship
from app.schemas.social import (
    FriendOut, FriendRequestOut, FriendRequestBody,
    FriendActionBody, UsernameSetBody,
)

router = APIRouter(prefix="/api/v1/friends", tags=["friends"])


@router.get("", response_model=list[FriendOut])
async def list_friends(
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
            friends.append(FriendOut(user_id=str(u.id), username=u.username, name=u.name))
    return friends


@router.post("/request", status_code=201)
async def send_request(
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
        if ex.status == "blocked":
            raise HTTPException(422, detail={"error": {"code": "BLOCKED", "message": "Blocked"}})
        if ex.status == "pending":
            raise HTTPException(409, detail={"error": {"code": "REQUEST_ALREADY_SENT", "message": "Request already sent"}})

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
async def get_requests(
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


@router.patch("/{friendship_id}")
async def respond_to_request(
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
async def search_user(
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
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
async def set_username(
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
