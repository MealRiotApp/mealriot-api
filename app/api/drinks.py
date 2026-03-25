import json
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import require_active_user
from app.core.database import get_db
from app.models.models import User, CustomDrink, FoodEntry, WaterLog
from app.schemas.entry import EntryOut
from app.middleware.rate_limit import limiter

router = APIRouter(prefix="/api/v1/drinks", tags=["drinks"])


class DrinkCreate(BaseModel):
    name: str
    name_he: str | None = None
    icon: str = "☕"
    volume_ml: int
    calories: int = 0
    sugar_g: float = 0
    protein_g: float = 0
    fat_g: float = 0
    carbs_g: float = 0
    counts_as_water: bool = True
    water_pct: int


class DrinkOut(BaseModel):
    id: str
    name: str
    name_he: str | None
    icon: str
    volume_ml: int
    calories: int
    sugar_g: float
    protein_g: float
    fat_g: float
    carbs_g: float
    counts_as_water: bool
    water_pct: int
    is_default: bool = False
    use_count: int = 0


class DrinkParseRequest(BaseModel):
    text: str


class DrinkParseResponse(BaseModel):
    name: str
    name_he: str
    icon: str
    volume_ml: int
    calories: int
    sugar_g: float
    protein_g: float
    fat_g: float
    carbs_g: float
    water_pct: int


@router.get("", response_model=list[DrinkOut])
@limiter.limit("60/minute")
async def list_drinks(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    result = await db.execute(
        select(CustomDrink)
        .where(CustomDrink.user_id == current_user.id)
        .order_by(CustomDrink.is_default.desc(), CustomDrink.use_count.desc(), CustomDrink.name.asc())
    )
    return [
        DrinkOut(
            id=str(d.id), name=d.name, name_he=d.name_he, icon=d.icon,
            volume_ml=d.volume_ml, calories=d.calories, sugar_g=float(d.sugar_g),
            protein_g=float(d.protein_g), fat_g=float(d.fat_g),
            carbs_g=float(d.carbs_g), counts_as_water=d.counts_as_water,
            water_pct=d.water_pct, is_default=d.is_default, use_count=d.use_count,
        )
        for d in result.scalars().all()
    ]


@router.post("/parse", response_model=DrinkParseResponse)
@limiter.limit("10/minute")
async def parse_drink(
    request: Request,
    body: DrinkParseRequest,
    _current_user: User = Depends(require_active_user),
):
    """AI parses free text like 'beer 500ml' or 'tea with sugar 330ml' into drink data."""
    from app.services.ai_service import _get_client

    client = _get_client()
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": """You are a nutrition analyst for beverages. Parse the user's drink description.
Return a JSON object with:
- name: English name of the drink
- name_he: Hebrew name of the drink
- icon: single emoji that represents this drink (☕🍵🥤🍺🍷🧃🥛🧋🍶)
- volume_ml: volume in milliliters
- calories: total calories (integer)
- sugar_g: sugar in grams (1 decimal)
- protein_g: protein in grams (1 decimal)
- fat_g: fat in grams (1 decimal)
- carbs_g: total carbs in grams (1 decimal)
- water_pct: percentage of the drink that counts as water intake (integer, 0-100)
  For example: water=100, coffee/tea=95, beer=92, wine=85, juice=85, soda=90, milk=87

Be precise with nutritional data. Use standard serving databases.
If volume not specified, use standard serving size.
Return ONLY the JSON object."""},
            {"role": "user", "content": body.text},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content or "{}"
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        text = text.rsplit("```", 1)[0]

    try:
        data = json.loads(text.strip())
        return DrinkParseResponse(
            name=data.get("name", "Drink"),
            name_he=data.get("name_he", "משקה"),
            icon=data.get("icon", "🥤"),
            volume_ml=int(data.get("volume_ml", 250)),
            calories=int(data.get("calories", 0)),
            sugar_g=float(data.get("sugar_g", 0)),
            protein_g=float(data.get("protein_g", 0)),
            fat_g=float(data.get("fat_g", 0)),
            carbs_g=float(data.get("carbs_g", 0)),
            water_pct=int(data.get("water_pct", 100)),
        )
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(500, detail="Failed to parse drink")


@router.post("", response_model=DrinkOut, status_code=201)
@limiter.limit("60/minute")
async def create_drink(
    request: Request,
    body: DrinkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    drink = CustomDrink(
        user_id=current_user.id, name=body.name, name_he=body.name_he,
        icon=body.icon, volume_ml=body.volume_ml, calories=body.calories,
        sugar_g=body.sugar_g, protein_g=body.protein_g, fat_g=body.fat_g,
        carbs_g=body.carbs_g, counts_as_water=body.counts_as_water,
        water_pct=body.water_pct,
    )
    db.add(drink)
    await db.commit()
    await db.refresh(drink)
    return DrinkOut(
        id=str(drink.id), name=drink.name, name_he=drink.name_he, icon=drink.icon,
        volume_ml=drink.volume_ml, calories=drink.calories, sugar_g=float(drink.sugar_g),
        protein_g=float(drink.protein_g), fat_g=float(drink.fat_g),
        carbs_g=float(drink.carbs_g), counts_as_water=drink.counts_as_water,
        water_pct=drink.water_pct, is_default=drink.is_default, use_count=drink.use_count,
    )


@router.post("/{drink_id}/log", status_code=201)
@limiter.limit("60/minute")
async def log_drink(
    request: Request,
    drink_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    """Log a drink: create FoodEntry + atomically update WaterLog + increment use_count."""
    result = await db.execute(
        select(CustomDrink).where(CustomDrink.id == drink_id, CustomDrink.user_id == current_user.id)
    )
    drink = result.scalar_one_or_none()
    if not drink:
        raise HTTPException(404, detail="Drink not found")

    now = datetime.now(timezone.utc)
    water_ml = round(drink.volume_ml * drink.water_pct / 100) if drink.counts_as_water else 0
    items = [{
        "food_name": drink.name,
        "food_name_he": drink.name_he,
        "grams": drink.volume_ml,
        "calories": drink.calories,
        "protein_g": float(drink.protein_g),
        "fat_g": float(drink.fat_g),
        "carbs_g": float(drink.carbs_g),
        "confidence": "high",
    }]

    entry = FoodEntry(
        user_id=current_user.id,
        description=drink.name,
        source="drink",
        drink_id=drink.id,
        water_ml=water_ml,
        meal_type="snack",
        items=items,
        total_calories=drink.calories,
        total_protein_g=float(drink.protein_g),
        total_fat_g=float(drink.fat_g),
        total_carbs_g=float(drink.carbs_g),
        logged_at=now,
    )
    db.add(entry)

    # Update water log atomically
    if water_ml > 0:
        today = now.date()
        wl_result = await db.execute(
            select(WaterLog).where(WaterLog.user_id == current_user.id, WaterLog.date == today)
        )
        wl = wl_result.scalar_one_or_none()
        if wl:
            wl.amount_ml = wl.amount_ml + water_ml
        else:
            db.add(WaterLog(user_id=current_user.id, date=today, amount_ml=water_ml))

    # Increment use_count via SQL expression (race-safe)
    drink.use_count = CustomDrink.use_count + 1

    await db.commit()
    await db.refresh(entry)
    return EntryOut.model_validate(entry).model_dump(mode="json")


@router.delete("/{drink_id}", status_code=204)
@limiter.limit("60/minute")
async def delete_drink(
    request: Request,
    drink_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    result = await db.execute(
        select(CustomDrink).where(CustomDrink.id == drink_id, CustomDrink.user_id == current_user.id)
    )
    drink = result.scalar_one_or_none()
    if not drink:
        raise HTTPException(404, detail="Drink not found")
    if drink.is_default:
        raise HTTPException(400, detail="Cannot delete default drink")
    # Null out drink_id on any food entries referencing this drink
    from sqlalchemy import update
    await db.execute(
        update(FoodEntry)
        .where(FoodEntry.drink_id == drink.id)
        .values(drink_id=None)
    )
    await db.delete(drink)
    await db.commit()
