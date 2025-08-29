from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.services.excluded_keywords_service import ExcludedKeywordsService
from app.schemas.excluded_keyword import (
    ExcludedKeywordCreate,
    ExcludedKeywordResponse,
    ExcludedKeywordListResponse,
)

router = APIRouter()


@router.get("/", response_model=ExcludedKeywordListResponse)
async def list_excluded_keywords(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    svc = ExcludedKeywordsService(db)
    svc.seed_defaults_if_empty(str(current_user.id))
    items = svc.list_keywords(str(current_user.id))
    return {
        "items": [
            ExcludedKeywordResponse(id=str(i.id), keyword=i.keyword, created_at=i.created_at)
            for i in items
        ]
    }


@router.post("/", response_model=ExcludedKeywordResponse)
async def add_excluded_keyword(
    payload: ExcludedKeywordCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    svc = ExcludedKeywordsService(db)
    item = svc.add_keyword(str(current_user.id), payload.keyword)
    return ExcludedKeywordResponse(id=str(item.id), keyword=item.keyword, created_at=item.created_at)


@router.delete("/{keyword_id}")
async def delete_excluded_keyword(
    keyword_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    svc = ExcludedKeywordsService(db)
    deleted = svc.delete_keyword(str(current_user.id), keyword_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return {"message": "Deleted"}


@router.post("/reset", response_model=ExcludedKeywordListResponse)
async def reset_excluded_keywords(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    svc = ExcludedKeywordsService(db)
    svc.reset_defaults(str(current_user.id))
    items = svc.list_keywords(str(current_user.id))
    return {
        "items": [
            ExcludedKeywordResponse(id=str(i.id), keyword=i.keyword, created_at=i.created_at)
            for i in items
        ]
    }
