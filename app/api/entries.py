import random
from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import require_active_user
from app.core.database import get_db
from app.models.models import User
from app.schemas.entry import EntryCreate, EntryUpdate, EntryOut, EntriesListResponse, DrinkSuggestion, EntryCreateResponse
from app.services.entries_service import create_entry, list_entries_for_date, update_entry, delete_entry
from app.middleware.rate_limit import limiter

router = APIRouter(prefix="/api/v1/entries", tags=["entries"])

REACTIONS = {
    "en": [
        "Logged it!",
        "Got it! Keep going",
        "Nice choice",
        "Noted! Looking good today",
        "Added to the log",
    ],
    "he": [
        "תועד!",
        "קיבלתי! תמשיך ככה",
        "בחירה טובה",
        "תועד! נראה טוב היום",
        "נוסף ליומן",
    ],
}


@router.post("", status_code=201)
@limiter.limit("60/minute")
async def create(
    request: Request,
    body: EntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    result = await create_entry(db, current_user, body.model_dump())
    lang = current_user.language or "en"
    reactions = REACTIONS.get(lang, REACTIONS["en"])
    reaction = random.choice(reactions)

    entries_out = [EntryOut.model_validate(e).model_dump(mode="json") for e in result["entries"]]
    return JSONResponse(status_code=201, content={
        "entries": entries_out,
        "drink_suggestions": result["drink_suggestions"],
        "reaction": reaction,
    })


@router.get("", response_model=EntriesListResponse)
@limiter.limit("60/minute")
async def list_for_day(
    request: Request,
    date: date,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    entries = await list_entries_for_date(db, current_user.id, date)
    return EntriesListResponse(entries=entries)


@router.patch("/{entry_id}", response_model=EntryOut)
@limiter.limit("60/minute")
async def update(
    request: Request,
    entry_id: UUID,
    body: EntryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    items = [i.model_dump() for i in body.items]
    return await update_entry(db, current_user.id, entry_id, items)


@router.delete("/{entry_id}", status_code=204)
@limiter.limit("60/minute")
async def delete(
    request: Request,
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    await delete_entry(db, current_user.id, entry_id)
