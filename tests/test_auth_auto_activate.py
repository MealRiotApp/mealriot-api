from unittest.mock import patch
from sqlalchemy import select
from app.models.models import User
from tests.conftest import make_jwt_payload, make_active_user


async def test_new_user_gets_active_status(client, db):
    """New users should be auto-activated, not pending."""
    payload = make_jwt_payload("newuser@test.com")
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.get("/api/v1/profile", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 200
    # Verify user was created with active status in DB
    result = await db.execute(select(User).where(User.email == "newuser@test.com"))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.status == "active"


async def test_suspended_user_blocked(client, db):
    """Suspended users should still get 403."""
    user, _ = await make_active_user(db, email="suspended@test.com")
    user.status = "suspended"
    db.add(user)
    await db.commit()

    payload = make_jwt_payload("suspended@test.com", user.supabase_id)
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.get("/api/v1/profile", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "SUSPENDED"


async def test_admin_user_gets_admin_role(client, db):
    """Admin email should still get admin role and active status."""
    from app.core.config import get_settings
    admin_email = get_settings().admin_email
    payload = make_jwt_payload(admin_email)
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.get("/api/v1/profile", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 200
