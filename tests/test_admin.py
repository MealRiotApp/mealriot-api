import pytest
import uuid
from unittest.mock import patch
from tests.conftest import make_jwt_payload
from app.models.models import User
from sqlalchemy import select


async def _seed_admin(db, settings_admin_email: str) -> tuple[User, str]:
    """Seed an admin user and return (user, supabase_id)."""
    sid = str(uuid.uuid4())
    user = User(supabase_id=sid, email=settings_admin_email,
                name="Admin", role="admin", status="active")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, sid


async def test_admin_can_list_users(client, db):
    from app.core.config import get_settings
    admin_email = get_settings().admin_email
    _, sid = await _seed_admin(db, admin_email)

    payload = make_jwt_payload(admin_email, supabase_id=sid)
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.get("/api/v1/admin/users",
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_admin_can_activate_pending_user(client, db):
    from app.core.config import get_settings
    admin_email = get_settings().admin_email
    _, admin_sid = await _seed_admin(db, admin_email)

    pending_sid = str(uuid.uuid4())
    pending = User(supabase_id=pending_sid, email="pending2@example.com",
                   name="Pending", role="member", status="pending")
    db.add(pending)
    await db.commit()
    await db.refresh(pending)

    payload = make_jwt_payload(admin_email, supabase_id=admin_sid)
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.patch(
            f"/api/v1/admin/users/{pending.id}/status",
            json={"status": "active"},
            headers={"Authorization": "Bearer faketoken"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


async def test_admin_can_suspend_user(client, db):
    from app.core.config import get_settings
    admin_email = get_settings().admin_email
    _, admin_sid = await _seed_admin(db, admin_email)

    active_sid = str(uuid.uuid4())
    active_user = User(supabase_id=active_sid, email="active2@example.com",
                       name="Active", role="member", status="active")
    db.add(active_user)
    await db.commit()
    await db.refresh(active_user)

    payload = make_jwt_payload(admin_email, supabase_id=admin_sid)
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.patch(
            f"/api/v1/admin/users/{active_user.id}/status",
            json={"status": "suspended"},
            headers={"Authorization": "Bearer faketoken"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "suspended"


async def test_invalid_status_rejected(client, db):
    from app.core.config import get_settings
    admin_email = get_settings().admin_email
    _, admin_sid = await _seed_admin(db, admin_email)

    some_user = User(supabase_id=str(uuid.uuid4()), email="someuser@example.com",
                     name="Some", role="member", status="active")
    db.add(some_user)
    await db.commit()
    await db.refresh(some_user)

    payload = make_jwt_payload(admin_email, supabase_id=admin_sid)
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.patch(
            f"/api/v1/admin/users/{some_user.id}/status",
            json={"status": "invalid_value"},
            headers={"Authorization": "Bearer faketoken"},
        )
    assert resp.status_code == 400
