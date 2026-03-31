import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


async def test_parse_text_returns_items():
    from app.services.ai_service import parse_food_text

    mock_response = MagicMock()
    # AI returns per-100g values; server scales to actual grams
    mock_response.output_text = (
        '[{"food_name":"White bread","food_name_he":"לחם לבן","grams":30,'
        '"calories_per_100g":265,"protein_per_100g":8.5,"fat_per_100g":2.5,"carbs_per_100g":50.0,"confidence":"high"}]'
    )

    with patch("app.services.ai_service._get_client") as mock_client_fn:
        mock_client = AsyncMock()
        mock_client.responses.create = AsyncMock(return_value=mock_response)
        mock_client_fn.return_value = mock_client

        items = await parse_food_text("a slice of white bread")

    assert len(items) == 1
    assert items[0]["food_name"] == "White bread"
    # 265 * 30/100 = 79.5 → rounded to 80
    assert items[0]["calories"] == 80


async def test_parse_text_invalid_json_raises():
    from app.services.ai_service import parse_food_text
    from fastapi import HTTPException

    mock_response = MagicMock()
    mock_response.output_text = "not json at all"

    with patch("app.services.ai_service._get_client") as mock_client_fn:
        mock_client = AsyncMock()
        mock_client.responses.create = AsyncMock(return_value=mock_response)
        mock_client_fn.return_value = mock_client

        with pytest.raises(HTTPException) as exc_info:
            await parse_food_text("something")

    assert exc_info.value.status_code == 500


async def test_parse_image_returns_items():
    from app.services.ai_service import parse_food_image

    mock_response = MagicMock()
    # AI returns per-100g values; server scales to actual grams
    mock_response.output_text = (
        '[{"food_name":"Apple","food_name_he":"תפוח","grams":150,'
        '"calories_per_100g":52,"protein_per_100g":0.3,"fat_per_100g":0.2,"carbs_per_100g":14.0,"confidence":"medium"}]'
    )

    with patch("app.services.ai_service._get_client") as mock_client_fn:
        mock_client = AsyncMock()
        mock_client.responses.create = AsyncMock(return_value=mock_response)
        mock_client_fn.return_value = mock_client

        items = await parse_food_image(b"fake_image_bytes", "image/jpeg")

    assert len(items) == 1
    assert items[0]["food_name"] == "Apple"


async def test_parse_image_with_hint_returns_items():
    from app.services.ai_service import parse_food_image_with_hint

    mock_response = MagicMock()
    # AI returns per-100g values; server scales to actual grams
    mock_response.output_text = (
        '[{"food_name":"Caesar salad","food_name_he":"סלט קיסר","grams":250,'
        '"calories_per_100g":72,"protein_per_100g":3.2,"fat_per_100g":4.8,"carbs_per_100g":4.0,"confidence":"medium"}]'
    )

    with patch("app.services.ai_service._get_client") as mock_client_fn:
        mock_client = AsyncMock()
        mock_client.responses.create = AsyncMock(return_value=mock_response)
        mock_client_fn.return_value = mock_client

        items = await parse_food_image_with_hint(
            b"fake_image_bytes", "image/jpeg", "This is a caesar salad"
        )

    assert len(items) == 1
    assert items[0]["food_name"] == "Caesar salad"

    # Verify that both image and hint text were sent in the input
    call_kwargs = mock_client.responses.create.call_args.kwargs
    user_content = call_kwargs["input"][0]["content"]
    content_types = [c["type"] for c in user_content]
    assert "input_image" in content_types
    assert "input_text" in content_types


async def test_parse_text_with_quantity():
    from app.services.ai_service import parse_food_text

    mock_response = MagicMock()
    # AI returns per-100g values; server scales to actual grams (80g per slice)
    mock_response.output_text = json.dumps({
        "items": [
            {"food_name": "Pizza Slice", "food_name_he": "משולש פיצה",
             "grams": 80, "calories_per_100g": 270, "protein_per_100g": 11.0,
             "fat_per_100g": 13.0, "carbs_per_100g": 28.0, "confidence": "medium",
             "quantity": 3}
        ]
    })

    with patch("app.services.ai_service._get_client") as mock_client_fn:
        mock_client = AsyncMock()
        mock_client.responses.create = AsyncMock(return_value=mock_response)
        mock_client_fn.return_value = mock_client

        items = await parse_food_text("שלוש משולשי פיצה")

    assert len(items) == 1
    assert items[0]["food_name"] == "Pizza Slice"
    assert items[0]["quantity"] == 3
    # 270 * 80/100 = 216 per slice (server scales per-100g to actual grams)
    assert items[0]["calories"] == 216
