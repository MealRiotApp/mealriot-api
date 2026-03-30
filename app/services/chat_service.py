import json
import re
import logging
from datetime import date

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.models import User
from app.services.stats_service import get_daily_stats

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=get_settings().openai_api_key)
    return _client


_SYSTEM_TEMPLATE = """You are MealRiot AI, a friendly and concise nutrition assistant.
The user is tracking their food intake. Here is their context for today:

Daily goals: {cal_goal} kcal, {protein_goal}g protein, {fat_goal}g fat, {carbs_goal}g carbs
Today's intake so far: {cal_current} kcal, {protein_current}g protein, {fat_current}g fat, {carbs_current}g carbs

Guidelines:
- Be helpful, concise, and encouraging.
- Answer nutrition questions based on the user's goals and progress.
- If the user describes food they want to log, include a hidden block at the END of your response (after all visible text) in this exact format:
  <!--FOODS:[{{"food_name":"Apple","calories":95,"protein_g":0.5,"fat_g":0.3,"carbs_g":25,"grams":182}}]-->
- The FOODS block must be valid JSON array. Only include it when the user is clearly describing food to log.
- Do NOT mention the FOODS block to the user. It is invisible metadata.
- Keep responses short (2-4 sentences) unless the user asks for detail.
- You may respond in the same language the user writes in."""


async def _build_system_prompt(db: AsyncSession, user: User) -> str:
    today = date.today()
    stats = await get_daily_stats(db, user, today)
    return _SYSTEM_TEMPLATE.format(
        cal_goal=user.daily_cal_goal or 2000,
        protein_goal=user.daily_protein_goal_g or 120,
        fat_goal=user.daily_fat_goal_g or 70,
        carbs_goal=user.daily_carbs_goal_g or 250,
        cal_current=stats["total_calories"],
        protein_current=round(stats["total_protein_g"], 1),
        fat_current=round(stats["total_fat_g"], 1),
        carbs_current=round(stats["total_carbs_g"], 1),
    )


def _extract_foods(full_text: str) -> tuple[str, list[dict] | None]:
    """Extract <!--FOODS:[...]-->  block from AI response.
    Returns (clean_text, foods_or_None).
    """
    try:
        match = re.search(r"<!--FOODS:(\[.*?\])-->", full_text, re.DOTALL)
        if not match:
            return full_text, None
        foods = json.loads(match.group(1))
        clean = full_text[:match.start()] + full_text[match.end():]
        return clean.strip(), foods
    except Exception:
        logger.warning("Failed to parse FOODS block from chat response", exc_info=True)
        return full_text, None


async def stream_chat(
    db: AsyncSession,
    user: User,
    message: str,
    history: list[dict],
):
    """Async generator yielding SSE-formatted strings."""
    try:
        system_prompt = await _build_system_prompt(db, user)

        # Truncate history to last 20 messages
        truncated_history = history[-20:]

        input_messages = [
            *truncated_history,
            {"role": "user", "content": message},
        ]

        client = _get_client()
        full_text = ""

        stream = await client.responses.create(
            model="gpt-4o",
            instructions=system_prompt,
            input=input_messages,
            stream=True,
        )
        async for event in stream:
            if event.type == "response.output_text.delta":
                token = event.delta
                full_text += token
                yield f"data: {json.dumps({'token': token})}\n\n"

        # Check for food extraction
        _, foods = _extract_foods(full_text)
        if foods:
            yield f"data: {json.dumps({'foods': foods})}\n\n"

    except Exception:
        logger.exception("Chat stream error")
        yield f'data: {json.dumps({"error": "Sorry, I couldn\'t process that right now. Please try again."})}\n\n'
    finally:
        yield "data: [DONE]\n\n"
