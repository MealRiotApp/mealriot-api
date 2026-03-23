import pytest
from unittest.mock import AsyncMock, patch, MagicMock


MOCK_OFF_RESPONSE = {
    "status": 1,
    "product": {
        "product_name": "Coca-Cola",
        "nutriments": {
            "energy-kcal_100g": 42,
            "proteins_100g": 0.0,
            "fat_100g": 0.0,
            "carbohydrates_100g": 10.6,
        },
        "serving_quantity": 330,
    },
}


async def test_lookup_found_returns_item():
    from app.services.barcode_service import lookup_barcode

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_OFF_RESPONSE

    with patch("app.services.barcode_service._get_client") as mock_client_fn:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_fn.return_value = mock_client

        items = await lookup_barcode("5449000000996")

    assert len(items) == 1
    assert items[0]["food_name"] == "Coca-Cola"
    assert items[0]["confidence"] == "high"
    assert items[0]["grams"] == 330.0


async def test_lookup_not_found_raises_404():
    from app.services.barcode_service import lookup_barcode
    from fastapi import HTTPException

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": 0, "product": {}}

    with patch("app.services.barcode_service._get_client") as mock_client_fn:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_fn.return_value = mock_client

        with pytest.raises(HTTPException) as exc_info:
            await lookup_barcode("0000000000000")

    assert exc_info.value.status_code == 404
