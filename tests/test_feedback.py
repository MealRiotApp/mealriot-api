from unittest.mock import patch, AsyncMock
from tests.conftest import make_jwt_payload, make_active_user


async def test_feedback_sends_email(client, db):
    """Feedback endpoint should accept message and send email."""
    user, sid = await make_active_user(db)
    payload = make_jwt_payload(user.email, user.supabase_id)

    with patch("app.middleware.auth.decode_jwt", return_value=payload), \
         patch("app.services.feedback_service.send_feedback_email", new_callable=AsyncMock) as mock_send:
        resp = await client.post(
            "/api/v1/feedback",
            data={"message": "Something is broken"},
            headers={"Authorization": "Bearer fake"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args
    assert "Something is broken" in str(call_kwargs)


async def test_feedback_requires_message(client, db):
    """Feedback without message should return 422."""
    user, sid = await make_active_user(db)
    payload = make_jwt_payload(user.email, user.supabase_id)

    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.post(
            "/api/v1/feedback",
            data={},
            headers={"Authorization": "Bearer fake"},
        )
    assert resp.status_code == 422


async def test_feedback_with_screenshot(client, db):
    """Feedback with screenshot file should work."""
    user, sid = await make_active_user(db)
    payload = make_jwt_payload(user.email, user.supabase_id)

    fake_image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    with patch("app.middleware.auth.decode_jwt", return_value=payload), \
         patch("app.services.feedback_service.send_feedback_email", new_callable=AsyncMock) as mock_send:
        resp = await client.post(
            "/api/v1/feedback",
            data={"message": "Bug with screenshot"},
            files={"screenshot": ("screenshot.png", fake_image, "image/png")},
            headers={"Authorization": "Bearer fake"},
        )
    assert resp.status_code == 200
    mock_send.assert_called_once()


async def test_feedback_rejects_large_screenshot(client, db):
    """Screenshot over 5MB should be rejected."""
    user, sid = await make_active_user(db)
    payload = make_jwt_payload(user.email, user.supabase_id)

    large_file = b"\x00" * (6 * 1024 * 1024)  # 6MB

    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.post(
            "/api/v1/feedback",
            data={"message": "Too big"},
            files={"screenshot": ("big.png", large_file, "image/png")},
            headers={"Authorization": "Bearer fake"},
        )
    assert resp.status_code == 413
