from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import require_active_user
from app.core.database import get_db
from app.models.models import User

router = APIRouter(prefix="/api/v1/goals", tags=["goals"])


class GoalCalculateRequest(BaseModel):
    weight_kg: float
    height_cm: float
    age: int
    sex: str  # "male" | "female"
    activity_level: str  # sedentary | light | moderate | active | very_active
    goal: str  # lose | maintain | gain
    goal_weight_kg: float | None = None


class GoalCalculateResponse(BaseModel):
    daily_cal_goal: int
    daily_protein_goal_g: int
    daily_fat_goal_g: int
    daily_carbs_goal_g: int
    daily_water_goal_ml: int
    bmr: int
    tdee: int


ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}

GOAL_ADJUSTMENTS = {
    "lose": -500,
    "maintain": 0,
    "gain": 300,
}


@router.post("/calculate", response_model=GoalCalculateResponse)
async def calculate_goals(
    body: GoalCalculateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    # Mifflin-St Jeor BMR
    if body.sex == "male":
        bmr = 10 * body.weight_kg + 6.25 * body.height_cm - 5 * body.age + 5
    else:
        bmr = 10 * body.weight_kg + 6.25 * body.height_cm - 5 * body.age - 161

    multiplier = ACTIVITY_MULTIPLIERS.get(body.activity_level, 1.55)
    tdee = round(bmr * multiplier)
    adjustment = GOAL_ADJUSTMENTS.get(body.goal, 0)
    daily_cal = max(1200, tdee + adjustment)

    # Macro split: 30% protein, 25% fat, 45% carbs
    protein_g = round(daily_cal * 0.30 / 4)
    fat_g = round(daily_cal * 0.25 / 9)
    carbs_g = round(daily_cal * 0.45 / 4)

    # Water: 30ml per kg body weight, min 1500
    water_ml = max(1500, round(body.weight_kg * 30 / 100) * 100)

    # Save to user profile
    current_user.weight_kg = body.weight_kg
    current_user.height_cm = body.height_cm
    current_user.age = body.age
    current_user.activity_level = body.activity_level
    current_user.goal_weight_kg = body.goal_weight_kg
    current_user.daily_cal_goal = daily_cal
    current_user.daily_protein_goal_g = protein_g
    current_user.daily_fat_goal_g = fat_g
    current_user.daily_carbs_goal_g = carbs_g
    current_user.daily_water_goal_ml = water_ml
    current_user.onboarding_done = True
    await db.commit()

    return GoalCalculateResponse(
        daily_cal_goal=daily_cal,
        daily_protein_goal_g=protein_g,
        daily_fat_goal_g=fat_g,
        daily_carbs_goal_g=carbs_g,
        daily_water_goal_ml=water_ml,
        bmr=round(bmr),
        tdee=tdee,
    )
