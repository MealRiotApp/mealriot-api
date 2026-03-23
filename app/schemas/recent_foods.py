from pydantic import BaseModel
from datetime import datetime


class RecentFoodItem(BaseModel):
    food_name: str
    food_name_he: str | None
    grams: float
    calories: int
    protein_g: float
    fat_g: float
    carbs_g: float
    use_count: int
    last_used_at: datetime
    model_config = {"from_attributes": True}


class RecentFoodsResponse(BaseModel):
    items: list[RecentFoodItem]
