import pytest
import uuid
from sqlalchemy import select
from app.models.models import User, FoodEntry, RecentFood


async def test_create_user(db):
    user = User(
        supabase_id=str(uuid.uuid4()),
        email="test@example.com",
        name="Test User",
        role="member",
        status="pending",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    assert user.id is not None
    assert user.status == "pending"
    assert user.theme == "ocean"
    assert user.language == "en"


async def test_user_defaults(db):
    user = User(
        supabase_id=str(uuid.uuid4()),
        email="defaults@example.com",
        name="Defaults",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    assert user.role == "member"
    assert user.status == "active"
    assert user.theme == "ocean"


async def test_create_food_entry(db):
    user = User(supabase_id=str(uuid.uuid4()), email="food@example.com", name="Food User")
    db.add(user)
    await db.commit()

    entry = FoodEntry(
        user_id=user.id,
        description="ate bread",
        source="text",
        meal_type="breakfast",
        items=[{"food_name": "bread", "grams": 30, "calories": 79}],
        total_calories=79,
        total_protein_g=2.5,
        total_fat_g=0.8,
        total_carbs_g=15.0,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    assert entry.id is not None
    assert entry.total_calories == 79


async def test_recent_food_unique_constraint(db):
    user = User(supabase_id=str(uuid.uuid4()), email="recent@example.com", name="Recent User")
    db.add(user)
    await db.commit()

    rf1 = RecentFood(user_id=user.id, food_name="bread", grams=30,
                     calories=79, protein_g=2.5, fat_g=0.8, carbs_g=15.0)
    rf2 = RecentFood(user_id=user.id, food_name="bread", grams=30,
                     calories=79, protein_g=2.5, fat_g=0.8, carbs_g=15.0)
    db.add(rf1)
    await db.commit()
    db.add(rf2)
    with pytest.raises(Exception):  # IntegrityError for duplicate
        await db.commit()
