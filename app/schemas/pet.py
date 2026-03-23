from pydantic import BaseModel


class PetStatusResponse(BaseModel):
    mood: str
    active_cat: str
    current_streak: int
    longest_streak: int
    message: str
    message_type: str
    time_of_day_state: str


class CatInfo(BaseModel):
    name: str
    emoji: str
    unlocked: bool
    unlock_streak: int
    unlocked_at: str | None


class CollectionResponse(BaseModel):
    cats: list[CatInfo]
    active_cat: str


class SetActiveCatRequest(BaseModel):
    cat_name: str


class SetActiveCatResponse(BaseModel):
    active_cat: str


class EatingWindowItem(BaseModel):
    meal_type: str
    start_time: str
    end_time: str


class EatingWindowsResponse(BaseModel):
    windows: list[EatingWindowItem]


class UpdateEatingWindowsRequest(BaseModel):
    windows: list[EatingWindowItem]


class MessageResponse(BaseModel):
    message: str
    message_type: str
    cached: bool
