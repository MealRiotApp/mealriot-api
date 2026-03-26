from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_active_user
from app.core.database import get_db
from app.middleware.rate_limit import limiter
from app.models.models import User
from app.schemas.chat import ChatRequest
from app.services.chat_service import stream_chat

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("")
@limiter.limit("10/minute")
async def chat(
    request: Request,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    history = [{"role": m.role, "content": m.content} for m in body.history]
    return StreamingResponse(
        stream_chat(db, current_user, body.message, history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
