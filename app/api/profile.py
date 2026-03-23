from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import require_active_user
from app.core.database import get_db
from app.models.models import User
from app.schemas.profile import ProfileOut, ProfileUpdate

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
async def get_profile(current_user: User = Depends(require_active_user)):
    return current_user


@router.patch("", response_model=ProfileOut)
async def update_profile(
    body: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(current_user, field, value)
    await db.commit()
    await db.refresh(current_user)
    return current_user
