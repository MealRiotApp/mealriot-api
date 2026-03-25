from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Literal
from app.schemas.food import FoodItem


class EntryCreate(BaseModel):
    description: str
    source: Literal["text", "image", "barcode", "drink"]
    image_url: str | None = None
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"] = "snack"
    items: list[FoodItem]
    logged_at: datetime | None = None


class EntryUpdate(BaseModel):
    items: list[FoodItem]


class EntryOut(BaseModel):
    id: UUID
    description: str
    source: str
    image_url: str | None
    drink_id: UUID | None = None
    meal_type: str
    items: list[FoodItem]
    total_calories: int
    total_protein_g: float
    total_fat_g: float
    total_carbs_g: float
    logged_at: datetime
    model_config = {"from_attributes": True}


class EntriesListResponse(BaseModel):
    entries: list[EntryOut]
