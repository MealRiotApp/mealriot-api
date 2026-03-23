from pydantic import BaseModel
from uuid import UUID


class ProfileOut(BaseModel):
    id: UUID
    email: str
    name: str
    avatar_url: str | None
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
    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    language: str | None = None
    theme: str | None = None
    daily_cal_goal: int | None = None
    daily_protein_goal_g: int | None = None
    daily_fat_goal_g: int | None = None
    daily_carbs_goal_g: int | None = None
    age: int | None = None
    weight_kg: float | None = None
    height_cm: float | None = None
    activity_level: str | None = None
