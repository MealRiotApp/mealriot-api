import uuid
import json
from datetime import datetime, date as date_type, time as time_type
from sqlalchemy import String, Integer, Numeric, Text, DateTime, JSON, Date, Time, func, UniqueConstraint, ForeignKey
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class GUID(TypeDecorator):
    """Platform-independent GUID type. Uses PostgreSQL's UUID, uses CHAR(36) on other backends."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PGUUID
            return dialect.type_descriptor(PGUUID())
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return uuid.UUID(value) if not isinstance(value, uuid.UUID) else value


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    supabase_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, nullable=False, default="member")
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")
    theme: Mapped[str] = mapped_column(String, nullable=False, default="ocean")
    daily_cal_goal: Mapped[int | None] = mapped_column(Integer)
    daily_protein_goal_g: Mapped[int | None] = mapped_column(Integer)
    daily_fat_goal_g: Mapped[int | None] = mapped_column(Integer)
    daily_carbs_goal_g: Mapped[int | None] = mapped_column(Integer)
    age: Mapped[int | None] = mapped_column(Integer)
    weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 2))
    height_cm: Mapped[float | None] = mapped_column(Numeric(5, 2))
    activity_level: Mapped[str | None] = mapped_column(String)
    active_cat: Mapped[str] = mapped_column(String, nullable=False, default="whiskers")
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_log_date: Mapped[date_type | None] = mapped_column(Date, nullable=True)
    username: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    friend_code: Mapped[str | None] = mapped_column(String(10), unique=True, nullable=True)
    macro_bonus_enabled: Mapped[bool] = mapped_column(default=True)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="UTC")
    daily_water_goal_ml: Mapped[int] = mapped_column(Integer, nullable=False, default=2000)
    goal_weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 2))
    daily_summary: Mapped[str | None] = mapped_column(Text)
    summary_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    onboarding_done: Mapped[bool] = mapped_column(default=False)
    use_24h: Mapped[bool] = mapped_column(default=True)
    first_day_of_week: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0=Sunday, 1=Monday
    insight_refreshes_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    insight_last_date: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FoodEntry(Base):
    __tablename__ = "food_entries"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)  # text | image | barcode
    image_url: Mapped[str | None] = mapped_column(String)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    meal_type: Mapped[str] = mapped_column(String, nullable=False, default="snack")
    items: Mapped[dict] = mapped_column(JSON, nullable=False)
    total_calories: Mapped[int] = mapped_column(Integer, nullable=False)
    total_protein_g: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    total_fat_g: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    total_carbs_g: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RecentFood(Base):
    __tablename__ = "recent_foods"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    food_name: Mapped[str] = mapped_column(String, nullable=False)
    food_name_he: Mapped[str | None] = mapped_column(String)
    grams: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    calories: Mapped[int] = mapped_column(Integer, nullable=False)
    protein_g: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    fat_g: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    carbs_g: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "food_name", name="uq_recent_foods_user_food"),
    )


class CatUnlock(Base):
    __tablename__ = "cat_unlocks"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    cat_name: Mapped[str] = mapped_column(String(20), nullable=False)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "cat_name", name="uq_cat_unlocks_user_cat"),
    )


class EatingWindow(Base):
    __tablename__ = "eating_windows"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    meal_type: Mapped[str] = mapped_column(String, nullable=False)
    start_time: Mapped[time_type] = mapped_column(Time, nullable=False)
    end_time: Mapped[time_type] = mapped_column(Time, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "meal_type", name="uq_eating_windows_user_meal"),
    )


class Friendship(Base):
    __tablename__ = "friendships"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    requester_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    addressee_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("requester_id", "addressee_id", name="uq_friendships_pair"),
    )


class CompetitionGroup(Base):
    __tablename__ = "competition_groups"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CompetitionMember(Base):
    __tablename__ = "competition_members"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("competition_groups.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_competition_members_pair"),
    )


class DailyPoints(Base):
    __tablename__ = "daily_points"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    calorie_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    logging_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    macro_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_daily_points_user_date"),
    )


class WeeklySummary(Base):
    __tablename__ = "weekly_summaries"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    group_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("competition_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    week_start: Mapped[date_type] = mapped_column(Date, nullable=False)
    total_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rank: Mapped[int | None] = mapped_column(Integer)
    winner: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "group_id", "week_start", name="uq_weekly_summary"),
    )


class WaterLog(Base):
    __tablename__ = "water_logs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    amount_ml: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_water_logs_user_date"),
    )


class WeightLog(Base):
    __tablename__ = "weight_logs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_weight_logs_user_date"),
    )


class CustomDrink(Base):
    __tablename__ = "custom_drinks"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    name_he: Mapped[str | None] = mapped_column(String)
    icon: Mapped[str] = mapped_column(String, nullable=False, default="☕")
    volume_ml: Mapped[int] = mapped_column(Integer, nullable=False)
    calories: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sugar_g: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    protein_g: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    fat_g: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    carbs_g: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    counts_as_water: Mapped[bool] = mapped_column(default=True)
    water_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
