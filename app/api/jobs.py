from datetime import date, timedelta
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.config import get_settings
from app.core.database import get_db
from app.models.models import (
    User, FoodEntry, CompetitionMember, CompetitionGroup,
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


def _calc_calorie_points(total_cal: int, goal: int) -> int:
    if goal == 0:
        return 0
    pct = total_cal / goal
    if 0.9 <= pct <= 1.1:
        return 6
    if 0.75 <= pct < 0.9:
        return 4
    if 1.1 < pct <= 1.25:
        return 3
    if 0.5 <= pct < 0.75:
        return 2
    if pct > 1.25:
        return 1
    return 0


def _calc_macro_points(user: User, total_protein: float, total_fat: float, total_carbs: float) -> int:
    if not user.macro_bonus_enabled:
        return 0
    pts = 0
    if user.daily_protein_goal_g and user.daily_protein_goal_g > 0:
        pct = total_protein / user.daily_protein_goal_g
        if 0.85 <= pct <= 1.15:
            pts += 1
    other_hit = False
    if user.daily_fat_goal_g and user.daily_fat_goal_g > 0:
        pct = total_fat / user.daily_fat_goal_g
        if 0.85 <= pct <= 1.15:
            other_hit = True
    if not other_hit and user.daily_carbs_goal_g and user.daily_carbs_goal_g > 0:
        pct = total_carbs / user.daily_carbs_goal_g
        if 0.85 <= pct <= 1.15:
            other_hit = True
    if other_hit:
        pts += 1
    return pts


@router.post("/compute-daily-points", dependencies=[Depends(_verify_secret)])
@limiter.limit("60/minute")
async def compute_daily_points(request: Request, db: AsyncSession = Depends(get_db)):
    today = date.today()
    # Get all users in active competitions
    member_result = await db.execute(
        select(CompetitionMember.user_id).distinct()
    )
    user_ids = [r[0] for r in member_result.all()]

    computed = 0
    for uid in user_ids:
        user = await db.get(User, uid)
        if not user:
            continue

        # Get entries for today
        entries_result = await db.execute(
            select(FoodEntry).where(
                FoodEntry.user_id == uid,
                func.date(FoodEntry.logged_at) == today,
            )
        )
        entries = entries_result.scalars().all()

        total_cal = sum(e.total_calories for e in entries)
        total_protein = sum(float(e.total_protein_g) for e in entries)
        total_fat = sum(float(e.total_fat_g) for e in entries)
        total_carbs = sum(float(e.total_carbs_g) for e in entries)

        goal = user.daily_cal_goal or 2000
        cal_pts = _calc_calorie_points(total_cal, goal)
        log_pts = min(len(entries), 2) if entries else 0
        macro_pts = _calc_macro_points(user, total_protein, total_fat, total_carbs)
        total_pts = cal_pts + log_pts + macro_pts

        # Upsert
        existing = await db.execute(
            select(DailyPoints).where(DailyPoints.user_id == uid, DailyPoints.date == today)
        )
        dp = existing.scalar_one_or_none()
        if dp:
            dp.calorie_points = cal_pts
            dp.logging_points = log_pts
            dp.macro_points = macro_pts
            dp.total_points = total_pts
        else:
            db.add(DailyPoints(
                user_id=uid, date=today,
                calorie_points=cal_pts, logging_points=log_pts,
                macro_points=macro_pts, total_points=total_pts,
            ))
        computed += 1

    await db.commit()
    return {"computed": computed, "date": today.isoformat()}


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
