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
  grams (number — per-unit weight. Use exact value if user specified, otherwise estimate. For beverages, use volume in ml)
  calories (integer kcal — per ONE unit)
  protein_g (number, 1 decimal — per ONE unit)
  fat_g (number, 1 decimal — per ONE unit)
  carbs_g (number, 1 decimal — per ONE unit)
  confidence ("high" if grams were explicit, "medium" if estimated from portion, "low" if uncertain)
  is_drink (boolean — true if the item is a beverage: coffee, tea, juice, cocktail, beer, wine, soda, smoothie, water, milk, energy drink, etc.)
  volume_ml (integer — only when is_drink is true, volume in milliliters per ONE unit)
  water_pct (integer 0-100 — only when is_drink is true, percentage that counts as water intake. Examples: water=100, coffee/tea=95, beer=92, wine=85, juice=85, soda=90, milk=87)
  quantity (integer — number of units. When the user specifies a count like "3 slices", "שלוש משולשי פיצה", "2 cups of coffee", set this to that number. All nutritional values above must be for ONE unit. Default to 1 if no count specified)

Rules:
- If grams are explicit (e.g. "150 גרם"), use that exactly.
- Convert portion descriptions (slice, cup, פרוסה) to grams using standard measures.
- For beverages, set grams equal to volume_ml.
- When the user specifies a quantity (e.g., "3 pizza slices", "שני מאפים", "2 cups of coffee"), always return ONE item with quantity set to that number. Never return separate identical items — use quantity instead.
- Use USDA as your reference.
- When uncertain, lean conservative.
- Always return a JSON object with an "items" key containing the array.
- Never include text outside the JSON."""

_IMAGE_SYSTEM_BASE = """You are a precise food vision analyst. You MUST respond with valid JSON only.

Analyze the food image and identify every distinct food item visible.
For each item, estimate portion size in grams using visual context:
  - Standard plate diameter (~26cm)
  - Visible utensils or hands for scale
  - Food density and typical serving sizes"""

_IMAGE_SYSTEM_FOOTER = """
Return the same JSON array structure as text parsing, plus a "visual_note" field per item.
Include is_drink, volume_ml, and water_pct fields for any beverages visible.
Flag confidence as "low" if items are obscured, stacked, or ambiguous."""

_IMAGE_SYSTEM = _IMAGE_SYSTEM_BASE + _IMAGE_SYSTEM_FOOTER

_IMAGE_HINT_ADDON = """
The user has provided a correction hint describing what is in the image.
Prioritize the user's hint over your own visual analysis — use it to correct
food identification, portion sizes, or any other detail. If the hint conflicts
with what you see, trust the hint."""

_IMAGE_HINT_SYSTEM = _IMAGE_SYSTEM_BASE + _IMAGE_HINT_ADDON + _IMAGE_SYSTEM_FOOTER


def _parse_json_response(content: str) -> list[dict]:
    try:
        # Strip markdown code fences GPT sometimes wraps around JSON
        text = content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            text = text.rsplit("```", 1)[0]
        result = json.loads(text.strip())
        if isinstance(result, dict) and "items" in result:
            result = result["items"]
        if isinstance(result, list):
            return result
        raise ValueError("Expected JSON array")
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "AI_PARSE_FAILED",
                              "message": f"AI returned invalid JSON: {str(e)[:100]}"}},
        )


async def parse_food_text(text: str) -> list[dict]:
    client = _get_client()
    response = await client.responses.create(
        model="gpt-4o",
        instructions=_TEXT_SYSTEM,
        input=[
            {"role": "user", "content": [
                {"type": "input_text", "text": text},
            ]},
        ],
        temperature=0,
    )
    return _parse_json_response(response.output_text)


async def parse_food_image(image_bytes: bytes, mime_type: str) -> list[dict]:
    client = _get_client()
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    response = await client.responses.create(
        model="gpt-4o",
        instructions=_IMAGE_SYSTEM,
        input=[
            {"role": "user", "content": [
                {"type": "input_image", "image_url": f"data:{mime_type};base64,{b64}"},
            ]},
        ],
        temperature=0,
    )
    return _parse_json_response(response.output_text)


async def parse_food_image_with_hint(
    image_bytes: bytes, mime_type: str, hint: str
) -> list[dict]:
    client = _get_client()
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    response = await client.responses.create(
        model="gpt-4o",
        instructions=_IMAGE_HINT_SYSTEM,
        input=[
            {"role": "user", "content": [
                {"type": "input_image", "image_url": f"data:{mime_type};base64,{b64}"},
                {"type": "input_text", "text": f"Correction: {hint}"},
            ]},
        ],
        temperature=0,
    )
    return _parse_json_response(response.output_text)
