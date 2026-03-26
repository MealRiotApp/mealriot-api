from pydantic import BaseModel
from typing import Literal


class FoodItem(BaseModel):
    food_name: str
    food_name_he: str | None = None
    grams: float
    calories: int
    protein_g: float
    fat_g: float
    carbs_g: float
    confidence: Literal["high", "medium", "low"] = "medium"
    is_drink: bool = False
    volume_ml: int | None = None
    water_pct: int | None = None


class ParseTextRequest(BaseModel):
    text: str


class ParseTextResponse(BaseModel):
    items: list[FoodItem]


class ParseImageResponse(BaseModel):
    image_url: str
    items: list[FoodItem]


class BarcodeResponse(BaseModel):
    items: list[FoodItem]


class ReparseImageRequest(BaseModel):
    image_url: str
    hint: str
