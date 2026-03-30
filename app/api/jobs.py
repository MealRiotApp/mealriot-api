from datetime import date, timedelta
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.config import get_settings
from app.core.database import get_db
from app.models.models import (
    User, CompetitionMember, CompetitionGroup,
    DailyPoints, WeeklySummary,
)
from app.middleware.rate_limit import limiter

router = APIRouter(prefix="/internal/jobs", tags=["jobs"])


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


async def _verify_secret(x_internal_secret: str = Header(...)):
    settings = get_settings()
    if x_internal_secret != settings.internal_secret:
        raise HTTPException(403, detail="Forbidden")


@router.post("/compute-weekly-summary", dependencies=[Depends(_verify_secret)])
@limiter.limit("60/minute")
async def compute_weekly_summary(request: Request, db: AsyncSession = Depends(get_db)):
    today = date.today()
    ws = _week_start(today)
    we = ws + timedelta(days=6)

    groups_result = await db.execute(
        select(CompetitionGroup).where(CompetitionGroup.is_active == True)
    )
    groups = groups_result.scalars().all()

    written = 0
    for group in groups:
        members_result = await db.execute(
            select(CompetitionMember).where(CompetitionMember.group_id == group.id)
        )
        members = members_result.scalars().all()

        standings = []
        for m in members:
            pts_result = await db.execute(
                select(func.coalesce(func.sum(DailyPoints.total_points), 0)).where(
                    DailyPoints.user_id == m.user_id,
                    DailyPoints.date >= ws,
                    DailyPoints.date <= we,
                )
            )
            total = pts_result.scalar()
            standings.append({"user_id": m.user_id, "total_points": total, "joined_at": m.joined_at})

        standings.sort(key=lambda x: (-x["total_points"],))
        for i, s in enumerate(standings):
            rank = i + 1
            winner = rank == 1
            existing = await db.execute(
                select(WeeklySummary).where(
                    WeeklySummary.user_id == s["user_id"],
                    WeeklySummary.group_id == group.id,
                    WeeklySummary.week_start == ws,
                )
            )
            ws_row = existing.scalar_one_or_none()
            if ws_row:
                ws_row.total_points = s["total_points"]
                ws_row.rank = rank
                ws_row.winner = winner
            else:
                db.add(WeeklySummary(
                    user_id=s["user_id"], group_id=group.id,
                    week_start=ws, total_points=s["total_points"],
                    rank=rank, winner=winner,
                ))
            written += 1

    await db.commit()
    return {"written": written, "week_start": ws.isoformat()}
