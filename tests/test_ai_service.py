import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


async def test_parse_text_returns_items():
    from app.services.ai_service import parse_food_text

    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        '[{"food_name":"White bread","food_name_he":"לחם לבן","grams":30,'
        '"calories":79,"protein_g":2.5,"fat_g":0.8,"carbs_g":15.1,"confidence":"high"}]'
    )

    with patch("app.services.ai_service._get_client") as mock_client_fn:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_client_fn.return_value = mock_client

        items = await parse_food_text("a slice of white bread")

    assert len(items) == 1
    assert items[0]["food_name"] == "White bread"
    assert items[0]["calories"] == 79


async def test_parse_text_invalid_json_raises():
    from app.services.ai_service import parse_food_text
    from fastapi import HTTPException

    mock_response = MagicMock()
    mock_response.choices[0].message.content = "not json at all"

    with patch("app.services.ai_service._get_client") as mock_client_fn:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_client_fn.return_value = mock_client

        with pytest.raises(HTTPException) as exc_info:
            await parse_food_text("something")

    assert exc_info.value.status_code == 500


async def test_parse_image_returns_items():
    from app.services.ai_service import parse_food_image

    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        '[{"food_name":"Apple","food_name_he":"תפוח","grams":150,'
        '"calories":78,"protein_g":0.4,"fat_g":0.2,"carbs_g":21.0,"confidence":"medium"}]'
    )

    with patch("app.services.ai_service._get_client") as mock_client_fn:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_client_fn.return_value = mock_client

        items = await parse_food_image(b"fake_image_bytes", "image/jpeg")

    assert len(items) == 1
    assert items[0]["food_name"] == "Apple"


async def test_parse_text_with_quantity():
    from app.services.ai_service import parse_food_text

    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({
        "items": [
            {"food_name": "Pizza Slice", "food_name_he": "משולש פיצה",
             "grams": 80, "calories": 250, "protein_g": 10.0,
             "fat_g": 12.0, "carbs_g": 25.0, "confidence": "medium",
             "quantity": 3}
        ]
    })

    with patch("app.services.ai_service._get_client") as mock_client_fn:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_client_fn.return_value = mock_client

        items = await parse_food_text("שלוש משולשי פיצה")

    assert len(items) == 1
    assert items[0]["food_name"] == "Pizza Slice"
    assert items[0]["quantity"] == 3
    assert items[0]["calories"] == 250
