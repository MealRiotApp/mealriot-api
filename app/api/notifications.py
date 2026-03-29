from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import require_active_user
from app.core.database import get_db
from app.models.models import User, Announcement
from app.schemas.announcement import AnnouncementOut
from app.middleware.rate_limit import limiter

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("/announcements", response_model=list[AnnouncementOut])
@limiter.limit("60/minute")
async def get_active_announcements(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_active_user),
):
    result = await db.execute(
        select(Announcement)
        .where(Announcement.active == True)
        .order_by(Announcement.created_at.desc())
    )
    return result.scalars().all()
