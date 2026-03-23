import pytest
from unittest.mock import patch
from tests.conftest import make_jwt_payload, make_active_user
from app.models.models import RecentFood
from datetime import datetime, timezone


async def test_recent_foods_empty(client, db):
    user, sid = await make_active_user(db)

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.get("/api/v1/recent-foods",
                                headers={"Authorization": "Bearer faketoken"})

    assert resp.status_code == 200
    assert resp.json()["items"] == []


async def test_recent_foods_returns_top_8(client, db):
    user, sid = await make_active_user(db)

    for i in range(10):
        db.add(RecentFood(
            user_id=user.id, food_name=f"food{i}", grams=100,
            calories=100, protein_g=5.0, fat_g=3.0, carbs_g=10.0,
            use_count=i + 1, last_used_at=datetime.now(timezone.utc),
        ))
    await db.commit()

    with patch("app.middleware.auth.decode_jwt",
               return_value=make_jwt_payload(user.email, supabase_id=sid)):
        resp = await client.get("/api/v1/recent-foods?limit=8",
                                headers={"Authorization": "Bearer faketoken"})

    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 8
