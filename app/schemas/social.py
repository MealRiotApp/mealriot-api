from pydantic import BaseModel


class FriendOut(BaseModel):
    user_id: str
    username: str | None
    name: str


class FriendRequestOut(BaseModel):
    friendship_id: str
    requester: FriendOut
    created_at: str


class FriendRequestBody(BaseModel):
    username: str


class FriendActionBody(BaseModel):
    action: str  # accept | decline | block


class GroupCreateBody(BaseModel):
    name: str
    member_ids: list[str]


class GroupOut(BaseModel):
    group_id: str
    name: str
    member_count: int


class StandingOut(BaseModel):
    rank: int
    user_id: str
    name: str
    total_points: int
    days_logged: int
    days_in_week: int
    is_current_user: bool


class LeaderboardResponse(BaseModel):
    week_start: str
    standings: list[StandingOut]


class WeekHistoryItem(BaseModel):
    week_start: str
    standings: list[StandingOut]


class HistoryResponse(BaseModel):
    weeks: list[WeekHistoryItem]


class TodayPointsResponse(BaseModel):
    date: str
    calorie_points: int
    logging_points: int
    macro_points: int
    total_points: int


class WeekPointsResponse(BaseModel):
    week_start: str
    total_points: int
    days: list[dict]


class UsernameSetBody(BaseModel):
    username: str
