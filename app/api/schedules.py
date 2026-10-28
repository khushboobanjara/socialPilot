from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.business import Business
from app.models.content import ContentPost
from app.models.schedule import PostSchedule
from app.models.user import User
from app.schemas.schedule import ScheduleCreate, ScheduleOut

router = APIRouter(prefix="/api/schedules", tags=["Content calendar"])

def owned_post(post_id: int, owner_id: int, db: Session) -> ContentPost:
    post = db.scalar(select(ContentPost).join(Business, ContentPost.business_id == Business.id)
        .where(ContentPost.id == post_id, Business.owner_id == owner_id)
        .options(selectinload(ContentPost.variants), selectinload(ContentPost.business)))
    if post is None:
        raise HTTPException(404, "Content post not found")
    return post

def schedule_payload(row: PostSchedule) -> dict:
    variant = next((v for v in row.post.variants if v.platform == row.platform), None)
    return {"id": row.id, "post_id": row.post_id, "owner_id": row.owner_id,
        "platform": row.platform, "scheduled_at": row.scheduled_at, "timezone": row.timezone,
        "status": row.status, "note": row.note, "created_at": row.created_at,
        "topic": row.post.topic, "business_name": row.post.business.name if row.post.business else None,
        "caption_preview": variant.caption[:180] if variant else ""}

@router.post("", response_model=list[ScheduleOut], status_code=status.HTTP_201_CREATED)
def create_schedule(payload: ScheduleCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    post = owned_post(payload.post_id, user.id, db)
    if post.status != "approved":
        raise HTTPException(409, "Only owner-approved posts can be scheduled. Submit and approve the post first.")
    available = {v.platform for v in post.variants}
    platforms = list(dict.fromkeys(payload.platforms))
    missing = set(platforms) - available
    if missing:
        raise HTTPException(400, f"No saved content variant for: {', '.join(sorted(missing))}")
    try:
        tz = ZoneInfo(payload.timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(422, "Unknown timezone. Use an IANA timezone such as Asia/Kolkata.") from exc
    local_dt = payload.scheduled_at
    if local_dt.tzinfo is not None:
        local_dt = local_dt.astimezone(tz).replace(tzinfo=None)
    now_local = datetime.now(tz).replace(tzinfo=None)
    if local_dt <= now_local:
        raise HTTPException(422, "Choose a future date and time.")
    created = []
    for platform in platforms:
        row = PostSchedule(post_id=post.id, owner_id=user.id, platform=platform,
            scheduled_at=local_dt, timezone=payload.timezone, status="scheduled", note=payload.note.strip())
        db.add(row)
        created.append(row)
    db.commit()
    for row in created:
        db.refresh(row)
    return [schedule_payload(row) for row in created]

@router.get("", response_model=list[ScheduleOut])
def list_schedules(start: datetime | None = Query(default=None), end: datetime | None = Query(default=None),
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(PostSchedule).where(PostSchedule.owner_id == user.id).options(
        selectinload(PostSchedule.post).selectinload(ContentPost.variants),
        selectinload(PostSchedule.post).selectinload(ContentPost.business)).order_by(PostSchedule.scheduled_at.asc())
    if start is not None:
        stmt = stmt.where(PostSchedule.scheduled_at >= start.replace(tzinfo=None))
    if end is not None:
        stmt = stmt.where(PostSchedule.scheduled_at < end.replace(tzinfo=None))
    rows = db.scalars(stmt).all()
    return [schedule_payload(row) for row in rows]

@router.delete("/{schedule_id}", response_model=ScheduleOut)
def cancel_schedule(schedule_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.scalar(select(PostSchedule).where(PostSchedule.id == schedule_id, PostSchedule.owner_id == user.id)
        .options(selectinload(PostSchedule.post).selectinload(ContentPost.variants),
                 selectinload(PostSchedule.post).selectinload(ContentPost.business)))
    if row is None:
        raise HTTPException(404, "Scheduled item not found")
    if row.status != "scheduled":
        raise HTTPException(409, "Only queued scheduled items can be cancelled")
    row.status = "cancelled"
    db.commit()
    db.refresh(row)
    return schedule_payload(row)
