from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import require_admin
from app.core.database import get_db
from app.models.models import User, Announcement
from app.schemas.user import UserOut, UserStatusUpdate
from app.schemas.announcement import AnnouncementCreate, AnnouncementUpdate, AnnouncementOut
from app.middleware.rate_limit import limiter

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

VALID_STATUSES = {"active", "suspended"}


@router.get("/users", response_model=list[UserOut])
@limiter.limit("60/minute")
async def list_users(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).order_by(User.created_at))
    return result.scalars().all()


@router.patch("/users/{user_id}/status", response_model=UserOut)
@limiter.limit("60/minute")
async def update_user_status(
    request: Request,
    user_id: UUID,
    body: UserStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    if body.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_STATUS",
                              "message": f"Status must be one of: {', '.join(VALID_STATUSES)}"}},
        )
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "User not found"}},
        )
    user.status = body.status
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/announcements", response_model=AnnouncementOut, status_code=201)
@limiter.limit("60/minute")
async def create_announcement(
    request: Request,
    body: AnnouncementCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    ann = Announcement(title=body.title, body=body.body)
    db.add(ann)
    await db.commit()
    await db.refresh(ann)
    return ann


@router.get("/announcements", response_model=list[AnnouncementOut])
@limiter.limit("60/minute")
async def list_announcements(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(Announcement).order_by(Announcement.created_at.desc())
    )
    return result.scalars().all()


@router.patch("/announcements/{announcement_id}", response_model=AnnouncementOut)
@limiter.limit("60/minute")
async def update_announcement(
    request: Request,
    announcement_id: UUID,
    body: AnnouncementUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(Announcement).where(Announcement.id == announcement_id)
    )
    ann = result.scalar_one_or_none()
    if not ann:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Announcement not found"}},
        )
    if body.title is not None:
        ann.title = body.title
    if body.body is not None:
        ann.body = body.body
    if body.active is not None:
        ann.active = body.active
    await db.commit()
    await db.refresh(ann)
    return ann
