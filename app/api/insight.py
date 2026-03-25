from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import require_active_user
from app.core.database import get_db
from app.models.models import User
from app.services.summary_service import update_user_summary
from app.middleware.rate_limit import limiter

router = APIRouter(prefix="/api/v1/insight", tags=["insight"])

MAX_USER_REFRESHES = 5


class InsightResponse(BaseModel):
    summary: str
    suggestion: str
    source: str
    refreshes_left: int


STATIC_SUGGESTIONS = {
    "en": [
        "Try to balance your meals throughout the day",
        "Remember to stay hydrated between meals",
        "A mix of protein and fiber keeps you full longer",
    ],
    "he": [
        "נסו לפזר את הארוחות לאורך היום",
        "זכרו לשתות מים בין הארוחות",
        "שילוב של חלבון וסיבים שומר על תחושת שובע",
    ],
}


def _reset_if_new_day(user: User) -> None:
    today = date.today().isoformat()
    if user.insight_last_date != today:
        user.insight_refreshes_today = 0
        user.insight_last_date = today


@router.get("/today", response_model=InsightResponse)
@limiter.limit("10/minute")
async def get_daily_insight(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    _reset_if_new_day(current_user)
    refreshes_left = max(0, MAX_USER_REFRESHES - (current_user.insight_refreshes_today or 0))

    summary = await update_user_summary(db, current_user)
    if not summary:
        summary = "No data yet for today."

    try:
        from app.services.ai_service import _get_client
        lang = "Hebrew" if current_user.language == "he" else "English"
        client = _get_client()
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You are a nutrition coach for a calorie tracking app. "
                    "Based on the user's day summary, give ONE specific, actionable tip for their next meal or the rest of the day. "
                    "Max 2 sentences. Be specific to what they ate. Friendly and encouraging tone. "
                    "Never say 'great job'. Never guilt. "
                    f"Respond in {lang}."
                )},
                {"role": "user", "content": summary},
            ],
            temperature=0.7,
            max_tokens=100,
        )
        suggestion = response.choices[0].message.content.strip()
        await db.commit()
        return InsightResponse(summary=summary, suggestion=suggestion, source="ai", refreshes_left=refreshes_left)
    except Exception:
        import random
        lang = current_user.language or "en"
        pool = STATIC_SUGGESTIONS.get(lang, STATIC_SUGGESTIONS["en"])
        await db.commit()
        return InsightResponse(summary=summary, suggestion=random.choice(pool), source="static", refreshes_left=refreshes_left)


@router.post("/refresh", response_model=InsightResponse)
@limiter.limit("10/minute")
async def refresh_insight(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    _reset_if_new_day(current_user)

    if (current_user.insight_refreshes_today or 0) >= MAX_USER_REFRESHES:
        raise HTTPException(429, detail={"error": {"code": "REFRESH_LIMIT", "message": "Daily refresh limit reached"}})

    current_user.insight_refreshes_today = (current_user.insight_refreshes_today or 0) + 1
    refreshes_left = max(0, MAX_USER_REFRESHES - current_user.insight_refreshes_today)

    summary = await update_user_summary(db, current_user)
    if not summary:
        summary = "No data yet for today."

    try:
        from app.services.ai_service import _get_client
        lang = "Hebrew" if current_user.language == "he" else "English"
        client = _get_client()
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You are a nutrition coach for a calorie tracking app. "
                    "Based on the user's day summary, give ONE specific, actionable tip for their next meal or the rest of the day. "
                    "Max 2 sentences. Be specific to what they ate. Friendly and encouraging tone. "
                    "Never say 'great job'. Never guilt. "
                    f"Respond in {lang}."
                )},
                {"role": "user", "content": summary},
            ],
            temperature=0.8,
            max_tokens=100,
        )
        suggestion = response.choices[0].message.content.strip()
        await db.commit()
        return InsightResponse(summary=summary, suggestion=suggestion, source="ai", refreshes_left=refreshes_left)
    except Exception:
        import random
        lang = current_user.language or "en"
        pool = STATIC_SUGGESTIONS.get(lang, STATIC_SUGGESTIONS["en"])
        await db.commit()
        return InsightResponse(summary=summary, suggestion=random.choice(pool), source="static", refreshes_left=refreshes_left)
