from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import require_active_user
from app.core.database import get_db
from app.models.models import User, RecentFood
from app.schemas.recent_foods import RecentFoodsResponse
from app.middleware.rate_limit import limiter

router = APIRouter(prefix="/api/v1/recent-foods", tags=["recent-foods"])


@router.get("", response_model=RecentFoodsResponse)
@limiter.limit("60/minute")
async def get_recent_foods(
    request: Request,
    limit: int = Query(default=8, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    stmt = (
        select(RecentFood)
        .where(RecentFood.user_id == current_user.id)
        .order_by(RecentFood.use_count.desc(), RecentFood.last_used_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return RecentFoodsResponse(items=list(result.scalars().all()))
