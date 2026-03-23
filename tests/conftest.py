import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.core.database import Base, get_db
import uuid

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db: AsyncSession):
    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def make_jwt_payload(email: str, supabase_id: str | None = None) -> dict:
    return {
        "sub": supabase_id or str(uuid.uuid4()),
        "email": email,
        "user_metadata": {"full_name": "Test User", "avatar_url": None},
    }


async def make_active_user(db, email="user@test.com", role="member"):
    from app.models.models import User
    sid = str(uuid.uuid4())
    user = User(
        supabase_id=sid, email=email, name="Test User",
        role=role, status="active",
        daily_cal_goal=2000, daily_protein_goal_g=120,
        daily_fat_goal_g=78, daily_carbs_goal_g=180,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, sid
