import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


async def test_parse_text_returns_items():
    from app.services.ai_service import parse_food_text

    mock_response = MagicMock()
    mock_response.output_text = (
        '[{"food_name":"White bread","food_name_he":"לחם לבן","grams":30,'
        '"calories":79,"protein_g":2.5,"fat_g":0.8,"carbs_g":15.1,"confidence":"high"}]'
    )

    with patch("app.services.ai_service._get_client") as mock_client_fn:
        mock_client = AsyncMock()
        mock_client.responses.create = AsyncMock(return_value=mock_response)
        mock_client_fn.return_value = mock_client

        items = await parse_food_text("a slice of white bread")

    assert len(items) == 1
    assert items[0]["food_name"] == "White bread"
    assert items[0]["calories"] == 79


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
    mock_response.output_text = (
        '[{"food_name":"Apple","food_name_he":"תפוח","grams":150,'
        '"calories":78,"protein_g":0.4,"fat_g":0.2,"carbs_g":21.0,"confidence":"medium"}]'
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
    mock_response.output_text = (
        '[{"food_name":"Caesar salad","food_name_he":"סלט קיסר","grams":250,'
        '"calories":180,"protein_g":8.0,"fat_g":12.0,"carbs_g":10.0,"confidence":"medium"}]'
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
    mock_response.output_text = json.dumps({
        "items": [
            {"food_name": "Pizza Slice", "food_name_he": "משולש פיצה",
             "grams": 80, "calories": 250, "protein_g": 10.0,
             "fat_g": 12.0, "carbs_g": 25.0, "confidence": "medium",
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
    assert items[0]["calories"] == 250
