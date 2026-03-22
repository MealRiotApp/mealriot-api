from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.models.models import User


async def require_active_user(
    user: User = Depends(get_current_user),
) -> User:
    return user


async def require_admin(
    user: User = Depends(require_active_user),
) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "FORBIDDEN", "message": "Admin access required"}},
        )
    return user
