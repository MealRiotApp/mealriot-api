from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import require_active_user
from app.core.database import get_db
from app.models.models import User, CustomDrink


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


@router.get("", response_model=list[DrinkOut])
async def list_drinks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    result = await db.execute(
        select(CustomDrink).where(CustomDrink.user_id == current_user.id)
    )
    return [
        DrinkOut(
            id=str(d.id), name=d.name, name_he=d.name_he, icon=d.icon,
            volume_ml=d.volume_ml, calories=d.calories, sugar_g=float(d.sugar_g),
            protein_g=float(d.protein_g), fat_g=float(d.fat_g),
            carbs_g=float(d.carbs_g), counts_as_water=d.counts_as_water,
        )
        for d in result.scalars().all()
    ]


@router.post("", response_model=DrinkOut, status_code=201)
async def create_drink(
    body: DrinkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    drink = CustomDrink(
        user_id=current_user.id, name=body.name, name_he=body.name_he,
        icon=body.icon, volume_ml=body.volume_ml, calories=body.calories,
        sugar_g=body.sugar_g, protein_g=body.protein_g, fat_g=body.fat_g,
        carbs_g=body.carbs_g, counts_as_water=body.counts_as_water,
    )
    db.add(drink)
    await db.commit()
    await db.refresh(drink)
    return DrinkOut(
        id=str(drink.id), name=drink.name, name_he=drink.name_he, icon=drink.icon,
        volume_ml=drink.volume_ml, calories=drink.calories, sugar_g=float(drink.sugar_g),
        protein_g=float(drink.protein_g), fat_g=float(drink.fat_g),
        carbs_g=float(drink.carbs_g), counts_as_water=drink.counts_as_water,
    )


@router.delete("/{drink_id}", status_code=204)
async def delete_drink(
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
    await db.delete(drink)
    await db.commit()
