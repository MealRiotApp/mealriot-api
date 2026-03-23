from pydantic import BaseModel
from datetime import date
from app.schemas.entry import EntryOut


class DayStats(BaseModel):
    date: date
    total_calories: int
    total_protein_g: float
    total_fat_g: float
    total_carbs_g: float
    goal_calories: int | None
    goal_protein_g: int | None
    goal_fat_g: int | None
    goal_carbs_g: int | None
    entry_count: int


class DailyStatsResponse(BaseModel):
    date: date
    total_calories: int
    total_protein_g: float
    total_fat_g: float
    total_carbs_g: float
    goal_calories: int | None
    goal_protein_g: int | None
    goal_fat_g: int | None
    goal_carbs_g: int | None
    entries: list[EntryOut]


class RangeStatsResponse(BaseModel):
    days: list[DayStats]
