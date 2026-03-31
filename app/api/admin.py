import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import require_admin
from app.core.database import get_db
from app.models.models import User, Announcement, FoodEntry, RecentFood
from app.schemas.user import UserOut, UserStatusUpdate
from app.schemas.announcement import AnnouncementCreate, AnnouncementUpdate, AnnouncementOut
from app.middleware.rate_limit import limiter
from app.services.ai_service import parse_food_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

VALID_STATUSES = {"active", "suspended"}


@router.get("/users", response_model=list[UserOut])
@limiter.limit("60/minute")
async def list_users(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).order_by(User.created_at))
    return result.scalars().all()


@router.patch("/users/{user_id}/status", response_model=UserOut)
@limiter.limit("60/minute")
async def update_user_status(
    request: Request,
    user_id: UUID,
    body: UserStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    if body.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_STATUS",
                              "message": f"Status must be one of: {', '.join(VALID_STATUSES)}"}},
        )
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "User not found"}},
        )
    user.status = body.status
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/announcements", response_model=AnnouncementOut, status_code=201)
@limiter.limit("60/minute")
async def create_announcement(
    request: Request,
    body: AnnouncementCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    ann = Announcement(title=body.title, body=body.body)
    db.add(ann)
    await db.commit()
    await db.refresh(ann)
    return ann


@router.get("/announcements", response_model=list[AnnouncementOut])
@limiter.limit("60/minute")
async def list_announcements(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(Announcement).order_by(Announcement.created_at.desc())
    )
    return result.scalars().all()


@router.patch("/announcements/{announcement_id}", response_model=AnnouncementOut)
@limiter.limit("60/minute")
async def update_announcement(
    request: Request,
    announcement_id: UUID,
    body: AnnouncementUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(Announcement).where(Announcement.id == announcement_id)
    )
    ann = result.scalar_one_or_none()
    if not ann:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Announcement not found"}},
        )
    if body.title is not None:
        ann.title = body.title
    if body.body is not None:
        ann.body = body.body
    if body.active is not None:
        ann.active = body.active
    await db.commit()
    await db.refresh(ann)
    return ann


@router.post("/recalculate-entries")
@limiter.limit("5/minute")
async def recalculate_entries(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """One-time fix: re-detect nutrition for text/image entries via AI.

    Batches by unique food_name to minimize API calls. Skips barcode and drink
    entries since those weren't affected by the per-100g bug.
    """
    result = await db.execute(
        select(FoodEntry).where(FoodEntry.source.in_(["text", "image"]))
    )
    entries = list(result.scalars().all())

    food_cache: dict[str, dict] = {}
    updated = 0
    skipped = 0
    errors = []

    for entry in entries:
        items = entry.items
        if not isinstance(items, list):
            skipped += 1
            continue

        changed = False
        new_items = []
        for item in items:
            food_name = item.get("food_name", "")
            grams = item.get("grams", 100)
            if not food_name:
                new_items.append(item)
                continue

            cache_key = food_name.lower().strip()
            if cache_key not in food_cache:
                try:
                    ai_items = await parse_food_text(f"100g {food_name}")
                    if ai_items:
                        food_cache[cache_key] = ai_items[0]
                    else:
                        food_cache[cache_key] = {}
                except Exception as e:
                    logger.warning(f"AI re-detect failed for '{food_name}': {e}")
                    errors.append(food_name)
                    food_cache[cache_key] = {}

            ref = food_cache[cache_key]
            if not ref:
                new_items.append(item)
                continue

            ratio = grams / 100
            old_cal = item.get("calories", 0)
            new_cal = round(ref.get("calories", 0) * ratio)
            item["calories"] = new_cal
            item["protein_g"] = round(ref.get("protein_g", 0) * ratio, 1)
            item["fat_g"] = round(ref.get("fat_g", 0) * ratio, 1)
            item["carbs_g"] = round(ref.get("carbs_g", 0) * ratio, 1)
            if old_cal != new_cal:
                changed = True
            new_items.append(item)

        if changed:
            entry.items = new_items
            total_cal = sum(
                i.get("calories", 0) * i.get("quantity", 1) for i in new_items
            )
            total_p = sum(
                float(i.get("protein_g", 0)) * i.get("quantity", 1) for i in new_items
            )
            total_f = sum(
                float(i.get("fat_g", 0)) * i.get("quantity", 1) for i in new_items
            )
            total_c = sum(
                float(i.get("carbs_g", 0)) * i.get("quantity", 1) for i in new_items
            )
            entry.total_calories = total_cal
            entry.total_protein_g = round(total_p, 2)
            entry.total_fat_g = round(total_f, 2)
            entry.total_carbs_g = round(total_c, 2)
            updated += 1
        else:
            skipped += 1

    # Also fix recent_foods table
    rf_result = await db.execute(select(RecentFood))
    recent_foods = list(rf_result.scalars().all())
    rf_updated = 0
    for rf in recent_foods:
        cache_key = rf.food_name.lower().strip()
        ref = food_cache.get(cache_key)
        if not ref:
            try:
                ai_items = await parse_food_text(f"100g {rf.food_name}")
                if ai_items:
                    ref = ai_items[0]
                    food_cache[cache_key] = ref
            except Exception:
                continue
        if not ref:
            continue
        ratio = float(rf.grams) / 100
        rf.calories = round(ref.get("calories", 0) * ratio)
        rf.protein_g = round(ref.get("protein_g", 0) * ratio, 1)
        rf.fat_g = round(ref.get("fat_g", 0) * ratio, 1)
        rf.carbs_g = round(ref.get("carbs_g", 0) * ratio, 1)
        rf_updated += 1

    await db.commit()

    return {
        "entries_updated": updated,
        "entries_skipped": skipped,
        "recent_foods_updated": rf_updated,
        "unique_foods_detected": len(food_cache),
        "errors": errors,
    }
