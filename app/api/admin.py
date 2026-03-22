from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import require_admin
from app.core.database import get_db
from app.models.models import User
from app.schemas.user import UserOut, UserStatusUpdate

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

VALID_STATUSES = {"active", "suspended"}


@router.get("/users", response_model=list[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).order_by(User.created_at))
    return result.scalars().all()


@router.patch("/users/{user_id}/status", response_model=UserOut)
async def update_user_status(
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
