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
    goal: str  # aggressive_loss | moderate_loss | mild_loss | maintain | mild_gain | moderate_gain
    goal_weight_kg: float | None = None
    body_fat_pct: float | None = None  # Optional for Katch-McArdle
    macro_preset: str = "balanced"  # balanced | high_protein | keto | custom


class GoalCalculateResponse(BaseModel):
    daily_cal_goal: int
    daily_protein_goal_g: int
    daily_fat_goal_g: int
    daily_carbs_goal_g: int
    daily_water_goal_ml: int
    bmr: int
    tdee: int
    formula_used: str


ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}

# 6 goal options with calorie adjustments
GOAL_ADJUSTMENTS = {
    "aggressive_loss": -1000,
    "moderate_loss": -500,
    "mild_loss": -250,
    "maintain": 0,
    "mild_gain": 250,
    "moderate_gain": 500,
}

# Protein g/kg by goal (protein-first method)
PROTEIN_PER_KG = {
    "aggressive_loss": 2.0,
    "moderate_loss": 1.8,
    "mild_loss": 1.6,
    "maintain": 1.4,
    "mild_gain": 1.6,
    "moderate_gain": 1.8,
}


def _mifflin_st_jeor(weight_kg: float, height_cm: float, age: int, sex: str) -> float:
    if sex == "male":
        return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161


def _katch_mcardle(weight_kg: float, body_fat_pct: float) -> float:
    lean_mass = weight_kg * (1 - body_fat_pct / 100)
    return 370 + (21.6 * lean_mass)


def _calc_macros_protein_first(daily_cal: int, weight_kg: float, goal: str, preset: str) -> tuple[int, int, int]:
    """Protein-first method: set protein in g/kg, fat as %, carbs fill remainder."""
    if preset == "keto":
        protein_g = round(weight_kg * 1.6)
        fat_cal = daily_cal * 0.70
        fat_g = round(fat_cal / 9)
        carbs_g = max(20, round((daily_cal - protein_g * 4 - fat_g * 9) / 4))
        return protein_g, fat_g, carbs_g

    if preset == "high_protein":
        protein_g = round(weight_kg * 2.2)
        fat_g = round(daily_cal * 0.25 / 9)
        carbs_g = max(50, round((daily_cal - protein_g * 4 - fat_g * 9) / 4))
        return protein_g, fat_g, carbs_g

    # balanced (default) — protein-first
    protein_per_kg = PROTEIN_PER_KG.get(goal, 1.4)
    protein_g = round(weight_kg * protein_per_kg)
    fat_g = round(daily_cal * 0.25 / 9)
    remaining_cal = daily_cal - (protein_g * 4) - (fat_g * 9)
    carbs_g = max(50, round(remaining_cal / 4))

    return protein_g, fat_g, carbs_g


@router.post("/calculate", response_model=GoalCalculateResponse)
async def calculate_goals(
    body: GoalCalculateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    # Choose formula
    if body.body_fat_pct and body.body_fat_pct > 0:
        bmr = _katch_mcardle(body.weight_kg, body.body_fat_pct)
        formula_used = "katch_mcardle"
    else:
        bmr = _mifflin_st_jeor(body.weight_kg, body.height_cm, body.age, body.sex)
        formula_used = "mifflin_st_jeor"

    # TDEE
    multiplier = ACTIVITY_MULTIPLIERS.get(body.activity_level, 1.55)
    tdee = round(bmr * multiplier)

    # Calorie target with goal adjustment
    adjustment = GOAL_ADJUSTMENTS.get(body.goal, 0)
    daily_cal_raw = tdee + adjustment

    # Sex-specific safety floor
    min_cal = 1500 if body.sex == "male" else 1200
    daily_cal = max(min_cal, daily_cal_raw)

    # Macros — protein-first method
    protein_g, fat_g, carbs_g = _calc_macros_protein_first(
        daily_cal, body.weight_kg, body.goal, body.macro_preset
    )

    # Water: 33ml per kg, rounded to nearest 100, min 1500
    water_ml = max(1500, round(body.weight_kg * 33 / 100) * 100)

    # Save to profile
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
        formula_used=formula_used,
    )
