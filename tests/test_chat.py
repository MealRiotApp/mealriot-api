import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from tests.conftest import make_jwt_payload, make_active_user
from app.services.chat_service import _extract_foods


def _make_mock_stream(text_chunks: list[str] = None):
    """Build a mock OpenAI streaming context manager."""
    if text_chunks is None:
        text_chunks = ["Hello", " there"]

    mock_stream = AsyncMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=False)

    async def mock_events():
        for chunk in text_chunks:
            event = MagicMock()
            event.type = "content.delta"
            event.delta = chunk
            yield event

    mock_stream.__aiter__ = lambda self: mock_events()
    return mock_stream


def _patch_openai(mock_stream=None, side_effect=None):
    """Return a patch context manager for the OpenAI client."""
    if mock_stream is None:
        mock_stream = _make_mock_stream()

    p = patch("app.services.chat_service._get_client")

    class _Ctx:
        def __enter__(self_ctx):
            mock_get_client = p.start()
            mock_openai = AsyncMock()
            if side_effect:
                mock_openai.chat.completions.stream = MagicMock(side_effect=side_effect)
            else:
                mock_openai.chat.completions.stream = MagicMock(return_value=mock_stream)
            mock_get_client.return_value = mock_openai
            return mock_openai

        def __exit__(self_ctx, *args):
            p.stop()

    return _Ctx()


async def test_chat_returns_sse_stream(client, db):
    user, sid = await make_active_user(db)
    mock_stream = _make_mock_stream(["Hi"])

    with _patch_openai(mock_stream):
        with patch(
            "app.middleware.auth.decode_jwt",
            return_value=make_jwt_payload(user.email, supabase_id=sid),
        ):
            resp = await client.post(
                "/api/v1/chat",
                json={"message": "Hello"},
                headers={"Authorization": "Bearer faketoken"},
            )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "data:" in resp.text


async def test_chat_requires_auth(client, db):
    resp = await client.post("/api/v1/chat", json={"message": "Hello"})
    assert resp.status_code == 401


async def test_chat_empty_message_returns_422(client, db):
    user, sid = await make_active_user(db)
    with patch(
        "app.middleware.auth.decode_jwt",
        return_value=make_jwt_payload(user.email, supabase_id=sid),
    ):
        resp = await client.post(
            "/api/v1/chat",
            json={"message": ""},
            headers={"Authorization": "Bearer faketoken"},
        )
    assert resp.status_code == 422


async def test_chat_long_message_returns_422(client, db):
    user, sid = await make_active_user(db)
    with patch(
        "app.middleware.auth.decode_jwt",
        return_value=make_jwt_payload(user.email, supabase_id=sid),
    ):
        resp = await client.post(
            "/api/v1/chat",
            json={"message": "x" * 501},
            headers={"Authorization": "Bearer faketoken"},
        )
    assert resp.status_code == 422


async def test_chat_system_prompt_includes_user_goals(client, db):
    user, sid = await make_active_user(db)
    mock_stream = _make_mock_stream(["OK"])

    captured = []

    def capture_stream(**kwargs):
        captured.append(kwargs)
        return mock_stream

    with _patch_openai(side_effect=capture_stream):
        with patch(
            "app.middleware.auth.decode_jwt",
            return_value=make_jwt_payload(user.email, supabase_id=sid),
        ):
            resp = await client.post(
                "/api/v1/chat",
                json={"message": "What should I eat?"},
                headers={"Authorization": "Bearer faketoken"},
            )

    assert resp.status_code == 200
    assert len(captured) == 1
    messages = captured[0]["messages"]
    system_msg = messages[0]["content"]
    assert "2000" in system_msg  # calorie goal
    assert "120" in system_msg  # protein goal


class TestExtractFoods:
    def test_valid_json_block(self):
        text = 'Here is an apple.<!--FOODS:[{"food_name":"Apple","calories":95}]-->'
        clean, foods = _extract_foods(text)
        assert clean == "Here is an apple."
        assert foods is not None
        assert len(foods) == 1
        assert foods[0]["food_name"] == "Apple"

    def test_no_block(self):
        text = "Just a normal response with no food data."
        clean, foods = _extract_foods(text)
        assert clean == text
        assert foods is None

    def test_malformed_json(self):
        text = "Bad data<!--FOODS:[{broken json}]-->"
        clean, foods = _extract_foods(text)
        assert clean == text
        assert foods is None
