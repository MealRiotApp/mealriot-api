from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import require_active_user
from app.core.database import get_db
from app.models.models import User
from app.services.summary_service import update_user_summary

router = APIRouter(prefix="/api/v1/insight", tags=["insight"])


class InsightResponse(BaseModel):
    summary: str
    suggestion: str
    source: str  # "ai" | "static"


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


@router.get("/today", response_model=InsightResponse)
async def get_daily_insight(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    summary = await update_user_summary(db, current_user)
    if not summary:
        summary = "No data yet for today."

    # Try AI suggestion
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
        return InsightResponse(summary=summary, suggestion=suggestion, source="ai")
    except Exception:
        import random
        lang = current_user.language or "en"
        pool = STATIC_SUGGESTIONS.get(lang, STATIC_SUGGESTIONS["en"])
        return InsightResponse(summary=summary, suggestion=random.choice(pool), source="static")
