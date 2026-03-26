import pytest
from unittest.mock import patch, AsyncMock, MagicMock
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


async def test_parse_image(client, db):
    user, sid = await make_active_user(db)

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        with patch("app.api.food.parse_food_image", new_callable=AsyncMock,
                   return_value=MOCK_ITEMS):
            with patch("app.api.food.asyncio.to_thread", new_callable=AsyncMock,
                       return_value="https://example.com/food.jpg"):
                resp = await client.post(
                    "/api/v1/food/parse-image",
                    files={"image": ("food.jpg", b"fakejpeg", "image/jpeg")},
                    headers={"Authorization": "Bearer faketoken"},
                )

    assert resp.status_code == 200
    assert resp.json()["image_url"] == "https://example.com/food.jpg"
    assert resp.json()["items"][0]["food_name"] == "Bread"


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


async def test_reparse_image(client, db):
    user, sid = await make_active_user(db)

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        with patch("app.api.food.parse_food_image_with_hint", new_callable=AsyncMock,
                   return_value=MOCK_ITEMS):
            with patch("app.api.food.httpx.AsyncClient") as mock_httpx:
                mock_resp = AsyncMock()
                mock_resp.content = b"fake_image_bytes"
                mock_resp.headers = {"content-type": "image/jpeg"}
                mock_resp.raise_for_status = MagicMock()
                mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_httpx.return_value)
                mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
                mock_httpx.return_value.get = AsyncMock(return_value=mock_resp)

                resp = await client.post(
                    "/api/v1/food/re-parse-image",
                    json={"image_url": "https://example.com/food.jpg", "hint": "that's couscous"},
                    headers={"Authorization": "Bearer faketoken"},
                )

    assert resp.status_code == 200
    assert resp.json()["items"][0]["food_name"] == "Bread"


async def test_reparse_image_empty_hint_rejected(client, db):
    user, sid = await make_active_user(db)

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.post(
            "/api/v1/food/re-parse-image",
            json={"image_url": "https://example.com/food.jpg", "hint": "   "},
            headers={"Authorization": "Bearer faketoken"},
        )

    assert resp.status_code == 400


async def test_reparse_image_requires_auth(client, db):
    resp = await client.post(
        "/api/v1/food/re-parse-image",
        json={"image_url": "https://example.com/food.jpg", "hint": "test"},
    )
    assert resp.status_code == 401
