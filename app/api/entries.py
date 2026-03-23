from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import require_active_user
from app.core.database import get_db
from app.models.models import User
from app.schemas.entry import EntryCreate, EntryUpdate, EntryOut, EntriesListResponse
from app.services.entries_service import create_entry, list_entries_for_date, update_entry, delete_entry

router = APIRouter(prefix="/api/v1/entries", tags=["entries"])


@router.post("", response_model=EntryOut, status_code=201)
async def create(
    body: EntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    return await create_entry(db, current_user, body.model_dump())


@router.get("", response_model=EntriesListResponse)
async def list_for_day(
    date: date,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    entries = await list_entries_for_date(db, current_user.id, date)
    return EntriesListResponse(entries=entries)


@router.patch("/{entry_id}", response_model=EntryOut)
async def update(
    entry_id: UUID,
    body: EntryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    items = [i.model_dump() for i in body.items]
    return await update_entry(db, current_user.id, entry_id, items)


@router.delete("/{entry_id}", status_code=204)
async def delete(
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    await delete_entry(db, current_user.id, entry_id)
