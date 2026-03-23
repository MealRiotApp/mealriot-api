import json
import base64
from fastapi import HTTPException
from openai import AsyncOpenAI
from app.core.config import get_settings

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=get_settings().openai_api_key)
    return _client


_TEXT_SYSTEM = """You are a precise nutrition analyst. You MUST respond with valid JSON only — no prose, no markdown.
The user may write in Hebrew or English. Detect language automatically.

For each food item identified, return an object with:
  food_name (string, English)
  food_name_he (string, Hebrew)
  grams (number — use exact value if user specified, otherwise estimate)
  calories (integer kcal)
  protein_g (number, 1 decimal)
  fat_g (number, 1 decimal)
  carbs_g (number, 1 decimal)
  confidence ("high" if grams were explicit, "medium" if estimated from portion, "low" if uncertain)

Rules:
- If grams are explicit (e.g. "150 גרם"), use that exactly.
- Convert portion descriptions (slice, cup, פרוסה) to grams using standard measures.
- Use USDA as your reference.
- When uncertain, lean conservative.
- Always return a JSON array, even for a single item.
- Never include text outside the JSON."""

_IMAGE_SYSTEM = """You are a precise food vision analyst. You MUST respond with valid JSON only.

Analyze the food image and identify every distinct food item visible.
For each item, estimate portion size in grams using visual context:
  - Standard plate diameter (~26cm)
  - Visible utensils or hands for scale
  - Food density and typical serving sizes

Return the same JSON array structure as text parsing, plus a "visual_note" field per item.
Flag confidence as "low" if items are obscured, stacked, or ambiguous."""


def _parse_json_response(content: str) -> list[dict]:
    try:
        result = json.loads(content)
        if isinstance(result, list):
            return result
        raise ValueError("Expected JSON array")
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "AI_PARSE_FAILED",
                              "message": "AI returned invalid JSON"}},
        )


async def parse_food_text(text: str) -> list[dict]:
    client = _get_client()
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _TEXT_SYSTEM},
            {"role": "user", "content": text},
        ],
        temperature=0,
    )
    return _parse_json_response(response.choices[0].message.content)


async def parse_food_image(image_bytes: bytes, mime_type: str) -> list[dict]:
    client = _get_client()
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _IMAGE_SYSTEM},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                    }
                ],
            },
        ],
        temperature=0,
        max_tokens=1000,
    )
    return _parse_json_response(response.choices[0].message.content)
