import httpx
import random
from fastapi import HTTPException, Header, Depends, Request
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.config import get_settings
from app.core.database import get_db
from app.models.models import User, CustomDrink

_jwks_cache: dict | None = None


async def prefetch_jwks() -> None:
    """Called once at app startup to warm the JWKS cache asynchronously."""
    global _jwks_cache
    settings = get_settings()
    url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=10)
        response.raise_for_status()
        _jwks_cache = response.json()


def decode_jwt(token: str) -> dict:
    try:
        jwks = _jwks_cache
        return jwt.decode(
            token,
            jwks,
            algorithms=["RS256", "ES256"],
            options={"verify_aud": False},
        )
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Invalid or expired token"}},
        )


async def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Missing bearer token"}},
        )
    token = authorization.split(" ", 1)[1]

    # Dev token bypass — only works when DEV_MODE=true
    if token.startswith("dev-"):
        settings = get_settings()
        if getattr(settings, "dev_mode", False):
            supabase_id = token[4:]  # strip "dev-" prefix
            result = await db.execute(select(User).where(User.supabase_id == supabase_id))
            user = result.scalar_one_or_none()
            if user:
                if user.status == "suspended":
                    raise HTTPException(403, detail={"error": {"code": "SUSPENDED", "message": "Account suspended"}})
                request.state.user_id = str(user.id)
                return user
        raise HTTPException(401, detail={"error": {"code": "UNAUTHORIZED", "message": "Invalid dev token"}})

    payload = decode_jwt(token)

    supabase_id = payload.get("sub")
    if not supabase_id:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Token missing subject claim"}},
        )
    email = payload.get("email", "")
    meta = payload.get("user_metadata") or {}
    name = meta.get("full_name") or email.split("@")[0]
    avatar_url = meta.get("avatar_url")

    result = await db.execute(select(User).where(User.supabase_id == supabase_id))
    user = result.scalar_one_or_none()

    if user is None:
        settings = get_settings()
        role = "admin" if email == settings.admin_email else "member"
        status = "active"
        user = User(
            supabase_id=supabase_id,
            email=email,
            name=name,
            avatar_url=avatar_url,
            role=role,
            status=status,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Seed default water drink (best-effort)
        try:
            default_drink = CustomDrink(
                user_id=user.id,
                name="Glass of Water",
                name_he="כוס מים",
                icon="💧",
                volume_ml=250,
                calories=0,
                sugar_g=0, protein_g=0, fat_g=0, carbs_g=0,
                counts_as_water=True,
                water_pct=100,
                is_default=True,
                use_count=0,
            )
            db.add(default_drink)
            await db.commit()
            await db.refresh(user)
        except Exception:
            import logging
            logging.getLogger(__name__).warning("Failed to seed default drink for user %s", user.id)

        # Auto-set username from display name
        base_username = name[:30]
        for attempt in range(6):
            candidate = base_username if attempt == 0 else f"{name[:28]}{random.randint(10, 99)}"
            try:
                user.username = candidate
                await db.commit()
                await db.refresh(user)
                break
            except IntegrityError:
                await db.rollback()
                # re-fetch user after rollback
                result = await db.execute(select(User).where(User.supabase_id == supabase_id))
                user = result.scalar_one()

    if user.status == "suspended":
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "SUSPENDED",
                              "message": "Your account has been suspended"}},
        )
    request.state.user_id = str(user.id)
    return user
