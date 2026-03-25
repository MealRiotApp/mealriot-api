from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse


def _get_user_or_ip(request: Request) -> str:
    """Key function: use authenticated user ID if available, else client IP."""
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return user_id
    return get_remote_address(request)


def _get_ip(request: Request) -> str:
    """Key function: always use client IP (for unauthenticated routes)."""
    return get_remote_address(request)


limiter = Limiter(
    key_func=_get_user_or_ip,
    headers_enabled=True,
)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMITED",
                "message": "Too many requests. Try again later.",
            }
        },
        headers={"Retry-After": "60"},
    )
