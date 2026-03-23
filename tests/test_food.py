import pytest
from unittest.mock import patch, AsyncMock
from tests.conftest import make_jwt_payload, make_active_user


MOCK_ITEMS = [
    {"food_name": "Bread", "food_name_he": "לחם", "grams": 30,
     "calories": 79, "protein_g": 2.5, "fat_g": 0.8, "carbs_g": 15.1, "confidence": "high"}
]


async def test_parse_text(client, db):
    user, sid = await make_active_user(db)

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        with patch("app.api.food.parse_food_text", new_callable=AsyncMock,
                   return_value=MOCK_ITEMS):
            resp = await client.post(
                "/api/v1/food/parse-text",
                json={"text": "a slice of bread"},
                headers={"Authorization": "Bearer faketoken"},
            )

    assert resp.status_code == 200
    assert resp.json()["items"][0]["food_name"] == "Bread"


async def test_parse_text_empty_rejected(client, db):
    user, sid = await make_active_user(db)

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.post(
            "/api/v1/food/parse-text",
            json={"text": "   "},
            headers={"Authorization": "Bearer faketoken"},
        )

    assert resp.status_code == 400


async def test_barcode_found(client, db):
    user, sid = await make_active_user(db)

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        with patch("app.api.food.lookup_barcode", new_callable=AsyncMock,
                   return_value=MOCK_ITEMS):
            resp = await client.get(
                "/api/v1/food/barcode/5449000000996",
                headers={"Authorization": "Bearer faketoken"},
            )

    assert resp.status_code == 200
    assert resp.json()["items"][0]["food_name"] == "Bread"


async def test_parse_text_requires_auth(client, db):
    resp = await client.post("/api/v1/food/parse-text", json={"text": "bread"})
    assert resp.status_code == 401


async def test_parse_image_wrong_mime_rejected(client, db):
    user, sid = await make_active_user(db)

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.post(
            "/api/v1/food/parse-image",
            files={"image": ("test.gif", b"fakegif", "image/gif")},
            headers={"Authorization": "Bearer faketoken"},
        )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_IMAGE"
