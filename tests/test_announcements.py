import uuid
from unittest.mock import patch
from tests.conftest import make_jwt_payload, make_active_user
from app.models.models import User


async def _seed_admin(db, admin_email: str) -> tuple[User, str]:
    sid = str(uuid.uuid4())
    user = User(supabase_id=sid, email=admin_email,
                name="Admin", role="admin", status="active")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, sid


async def test_create_announcement(client, db):
    from app.core.config import get_settings
    admin_email = get_settings().admin_email
    _, sid = await _seed_admin(db, admin_email)

    payload = make_jwt_payload(admin_email, supabase_id=sid)
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.post(
            "/api/v1/admin/announcements",
            json={"title": "Hello World", "body": "First announcement"},
            headers={"Authorization": "Bearer faketoken"},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Hello World"
    assert data["body"] == "First announcement"
    assert data["active"] is True
    assert "id" in data


async def test_list_announcements_admin(client, db):
    from app.core.config import get_settings
    from app.models.models import Announcement

    admin_email = get_settings().admin_email
    _, sid = await _seed_admin(db, admin_email)

    # Seed announcements
    a1 = Announcement(title="Active one", body="body1", active=True)
    a2 = Announcement(title="Inactive one", body="body2", active=False)
    db.add_all([a1, a2])
    await db.commit()

    payload = make_jwt_payload(admin_email, supabase_id=sid)
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.get(
            "/api/v1/admin/announcements",
            headers={"Authorization": "Bearer faketoken"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


async def test_update_announcement(client, db):
    from app.core.config import get_settings
    from app.models.models import Announcement

    admin_email = get_settings().admin_email
    _, sid = await _seed_admin(db, admin_email)

    ann = Announcement(title="Old title", body="Old body", active=True)
    db.add(ann)
    await db.commit()
    await db.refresh(ann)

    payload = make_jwt_payload(admin_email, supabase_id=sid)
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.patch(
            f"/api/v1/admin/announcements/{ann.id}",
            json={"title": "New title", "active": False},
            headers={"Authorization": "Bearer faketoken"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "New title"
    assert data["active"] is False
    assert data["body"] == "Old body"


async def test_non_admin_cannot_create_announcement(client, db):
    user, sid = await make_active_user(db, email="regular@test.com", role="member")

    payload = make_jwt_payload("regular@test.com", supabase_id=sid)
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.post(
            "/api/v1/admin/announcements",
            json={"title": "Sneaky", "body": "Nope"},
            headers={"Authorization": "Bearer faketoken"},
        )
    assert resp.status_code == 403


async def test_user_gets_only_active_announcements(client, db):
    from app.models.models import Announcement

    user, sid = await make_active_user(db, email="viewer@test.com", role="member")

    a1 = Announcement(title="Active", body="Visible", active=True)
    a2 = Announcement(title="Hidden", body="Invisible", active=False)
    db.add_all([a1, a2])
    await db.commit()

    payload = make_jwt_payload("viewer@test.com", supabase_id=sid)
    with patch("app.middleware.auth.decode_jwt", return_value=payload):
        resp = await client.get(
            "/api/v1/notifications/announcements",
            headers={"Authorization": "Bearer faketoken"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Active"
