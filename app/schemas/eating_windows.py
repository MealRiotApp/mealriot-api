from pydantic import BaseModel


class EatingWindowItem(BaseModel):
    meal_type: str
    start_time: str
    end_time: str


class EatingWindowsResponse(BaseModel):
    windows: list[EatingWindowItem]


class UpdateEatingWindowsRequest(BaseModel):
    windows: list[EatingWindowItem]
