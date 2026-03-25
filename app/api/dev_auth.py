"""
Dev-only authentication bypass for automated testing (Playwright, etc.)
MUST be disabled in production via DEV_MODE=false env var.
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import get_settings
from app.core.database import get_db
from app.models.models import User
from app.middleware.rate_limit import limiter, _get_ip

router = APIRouter(prefix="/api/v1/dev", tags=["dev"])


class DevLoginRequest(BaseModel):
    email: str
    name: str = "Test User"


class DevLoginResponse(BaseModel):
    token: str
    user_id: str
    email: str


@router.post("/login", response_model=DevLoginResponse)
@limiter.limit("20/minute", key_func=_get_ip)
async def dev_login(
    request: Request,
    body: DevLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    if not getattr(settings, "dev_mode", False):
        raise HTTPException(403, detail="Dev login disabled in production")

    # Find or create user
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            supabase_id=f"dev-{uuid.uuid4()}",
            email=body.email,
            name=body.name,
            role="admin" if body.email == settings.admin_email else "member",
            status="active",  # Dev users are auto-approved
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # Return a dev token — the middleware will need to accept this
    token = f"dev-{user.supabase_id}"
    return DevLoginResponse(token=token, user_id=str(user.id), email=user.email)
