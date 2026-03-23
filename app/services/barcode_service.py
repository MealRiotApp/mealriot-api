import httpx
from fastapi import HTTPException

_OFF_BASE = "https://world.openfoodfacts.org/api/v0/product"

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=10)
    return _client


async def lookup_barcode(barcode: str) -> list[dict]:
    client = _get_client()
    resp = await client.get(f"{_OFF_BASE}/{barcode}.json")
    data = resp.json()

    if data.get("status") != 1 or not data.get("product"):
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "BARCODE_NOT_FOUND",
                              "message": f"Barcode {barcode} not found in Open Food Facts"}},
        )

    product = data["product"]
    nutriments = product.get("nutriments", {})
    kcal_100g = nutriments.get("energy-kcal_100g") or nutriments.get("energy-kcal") or 0
    protein_100g = nutriments.get("proteins_100g", 0) or 0
    fat_100g = nutriments.get("fat_100g", 0) or 0
    carbs_100g = nutriments.get("carbohydrates_100g", 0) or 0

    serving_g = product.get("serving_quantity") or 100
    try:
        serving_g = float(serving_g)
    except (TypeError, ValueError):
        serving_g = 100.0

    ratio = serving_g / 100.0

    return [
        {
            "food_name": product.get("product_name", "Unknown product"),
            "food_name_he": None,
            "grams": serving_g,
            "calories": round(kcal_100g * ratio),
            "protein_g": round(protein_100g * ratio, 1),
            "fat_g": round(fat_100g * ratio, 1),
            "carbs_g": round(carbs_100g * ratio, 1),
            "confidence": "high",
        }
    ]
