from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, desc
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import pytz

from app.core.database import get_db
from app.core.deps import get_current_admin_user
from app.models.user import User
from app.schemas.user import User as UserSchema

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/users", response_model=List[UserSchema])
def list_users(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
    q: Optional[str] = None,
    limit: int = 25,
    offset: int = 0,
    sort: str = "created_at",
    order: str = "desc",
):
    """List users (admin only) with pagination and optional search by email or name"""
    query = db.query(User)

    if q:
        like = f"%{q}%"
        query = query.filter(
            (User.email.ilike(like)) |
            (User.first_name.ilike(like)) |
            (User.last_name.ilike(like))
        )

    # Sorting
    sort_col = getattr(User, sort, User.created_at)
    if order.lower() == "desc":
        query = query.order_by(desc(sort_col))
    else:
        query = query.order_by(sort_col)

    users = query.offset(offset).limit(limit).all()
    return users

@router.patch("/users/{user_id}")
def toggle_user_active(
    user_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
):
    """Activate/deactivate a user. Prevent admin from deactivating self."""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if target.id == current_admin.id and payload.get("is_active") is False and current_admin.is_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admins cannot deactivate themselves")

    if "is_active" in payload:
        target.is_active = bool(payload["is_active"])
        db.commit()
        db.refresh(target)

    return {"id": str(target.id), "is_active": target.is_active}

@router.get("/stats/signups")
def signup_stats(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
    start: Optional[str] = None,
    end: Optional[str] = None,
    tz: str = "America/Lima",
):
    """Daily signup counts between start and end (inclusive)."""
    try:
        timezone = pytz.timezone(tz)
    except Exception:
        timezone = pytz.timezone("UTC")

    # default window: last 30 days
    now = datetime.now(timezone)
    if end:
        end_dt = timezone.localize(datetime.fromisoformat(end))
    else:
        end_dt = now
    if start:
        start_dt = timezone.localize(datetime.fromisoformat(start))
    else:
        start_dt = end_dt - timedelta(days=30)

    # Normalize to date boundaries (UTC for DB comparison)
    start_utc = start_dt.astimezone(pytz.UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    end_utc = end_dt.astimezone(pytz.UTC).replace(hour=23, minute=59, second=59, microsecond=999999)

    rows = (
        db.query(func.date(User.created_at).label("day"), func.count(User.id))
        .filter(User.created_at >= start_utc, User.created_at <= end_utc)
        .group_by(func.date(User.created_at))
        .order_by(func.date(User.created_at))
        .all()
    )

    # Build full day range
    result = []
    day = start_dt.date()
    while day <= end_dt.date():
        result.append({"day": day.isoformat(), "count": 0})
        day += timedelta(days=1)

    # Index rows, supporting SQLite (string) and Postgres (date)
    index = {}
    for r in rows:
        key = r[0]
        if hasattr(key, "isoformat"):
            key = key.isoformat()
        elif isinstance(key, str):
            key = str(key)
        else:
            key = str(key)
        index[key] = int(r[1])

    for item in result:
        if item["day"] in index:
            item["count"] = index[item["day"]]

    return {"start": start_dt.date().isoformat(), "end": end_dt.date().isoformat(), "tz": tz, "data": result}
