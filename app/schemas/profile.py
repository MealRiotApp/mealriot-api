from pydantic import BaseModel
from uuid import UUID


class ProfileOut(BaseModel):
    id: UUID
    email: str
    name: str
    avatar_url: str | None
    role: str
    username: str | None
    friend_code: str | None
    language: str
    theme: str
    daily_cal_goal: int | None
    daily_protein_goal_g: int | None
    daily_fat_goal_g: int | None
    daily_carbs_goal_g: int | None
    age: int | None
    weight_kg: float | None
    height_cm: float | None
    activity_level: str | None
    daily_water_goal_ml: int
    goal_weight_kg: float | None
    onboarding_done: bool
    use_24h: bool
    current_streak: int
    longest_streak: int
    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    language: str | None = None
    theme: str | None = None
    daily_cal_goal: int | None = None
    daily_protein_goal_g: int | None = None
    daily_fat_goal_g: int | None = None
    daily_carbs_goal_g: int | None = None
    daily_water_goal_ml: int | None = None
    age: int | None = None
    weight_kg: float | None = None
    height_cm: float | None = None
    activity_level: str | None = None
    goal_weight_kg: float | None = None
    use_24h: bool | None = None
