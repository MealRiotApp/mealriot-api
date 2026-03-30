import pytest
from unittest.mock import patch
from tests.conftest import make_jwt_payload
import uuid


async def test_health_requires_no_auth(client):
    resp = await client.get("/health")
    assert resp.status_code == 200


async def test_protected_endpoint_no_token(client):
    resp = await client.get("/api/v1/admin/users")
    assert resp.status_code == 401


async def test_protected_endpoint_invalid_token(client):
    resp = await client.get("/api/v1/admin/users",
                            headers={"Authorization": "Bearer not.a.real.token"})
    assert resp.status_code == 401


async def test_pending_user_not_blocked(client, db):
    """Users with legacy 'pending' status in DB are no longer blocked — they get FORBIDDEN (not admin)."""
    from app.models.models import User
    sid = str(uuid.uuid4())
    user = User(supabase_id=sid, email="pending@example.com",
                name="Pending", role="member", status="pending")
    db.add(user)
    await db.commit()

    payload = make_jwt_payload("pending@example.com", supabase_id=sid)
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.get("/api/v1/admin/users",
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


async def test_suspended_user_gets_403(client, db):
    from app.models.models import User
    sid = str(uuid.uuid4())
    user = User(supabase_id=sid, email="suspended@example.com",
                name="Suspended", role="member", status="suspended")
    db.add(user)
    await db.commit()

    payload = make_jwt_payload("suspended@example.com", supabase_id=sid)
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.get("/api/v1/admin/users",
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "SUSPENDED"


async def test_new_user_auto_created_as_active(client, db):
    """New users are auto-activated; non-admin gets FORBIDDEN (not admin) on admin endpoint."""
    from app.models.models import User
    from sqlalchemy import select
    sid = str(uuid.uuid4())
    payload = make_jwt_payload("brandnew@example.com", supabase_id=sid)
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.get("/api/v1/admin/users",
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
    # User should have been created in DB as active
    result = await db.execute(select(User).where(User.supabase_id == sid))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.status == "active"
    assert user.role == "member"


async def test_admin_email_auto_created_as_active(client, db):
    from app.models.models import User
    from sqlalchemy import select
    from app.core.config import get_settings
    admin_email = get_settings().admin_email
    sid = str(uuid.uuid4())
    payload = make_jwt_payload(admin_email, supabase_id=sid)
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.get("/api/v1/admin/users",
                                headers={"Authorization": "Bearer faketoken"})
    # Admin auto-created as active+admin, should be able to access admin endpoint
    assert resp.status_code == 200
    result = await db.execute(select(User).where(User.supabase_id == sid))
    user = result.scalar_one_or_none()
    assert user.role == "admin"
    assert user.status == "active"


async def test_non_admin_active_user_cannot_access_admin(client, db):
    from app.models.models import User
    sid = str(uuid.uuid4())
    user = User(supabase_id=sid, email="member@example.com",
                name="Member", role="member", status="active")
    db.add(user)
    await db.commit()

    payload = make_jwt_payload("member@example.com", supabase_id=sid)
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.get("/api/v1/admin/users",
                                headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
