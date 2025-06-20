from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.models.card_type import CardType
from app.schemas.card_type import (
    CardType as CardTypeSchema,
    CardTypeCreate,
    CardTypeUpdate
)

router = APIRouter()

@router.get("/", response_model=List[CardTypeSchema])
async def get_card_types(
    country_code: Optional[str] = None,
    active_only: bool = True,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all card types with optional filtering.
    
    Like browsing different types of cards - you can filter
    by country or show only active types.
    """
    query = db.query(CardType)
    
    if active_only:
        query = query.filter(CardType.is_active == True)
    
    if country_code:
        # Show both global and country-specific card types
        query = query.filter(
            (CardType.country == country_code) |
            (CardType.country == "GLOBAL")
        )
    
    return query.order_by(CardType.name).all()

@router.post("/", response_model=CardTypeSchema)
async def create_card_type(
    card_type_create: CardTypeCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new card type (admin only)"""
    # TODO: Add admin permission check
    card_type = CardType(**card_type_create.dict())
    db.add(card_type)
    db.commit()
    db.refresh(card_type)
    return card_type

@router.get("/{card_type_id}", response_model=CardTypeSchema)
async def get_card_type(
    card_type_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific card type by ID"""
    card_type = db.query(CardType).filter(
        CardType.id == card_type_id
    ).first()
    
    if not card_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card type not found"
        )
    
    return card_type

@router.put("/{card_type_id}", response_model=CardTypeSchema)
async def update_card_type(
    card_type_id: uuid.UUID,
    card_type_update: CardTypeUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a card type (admin only)"""
    # TODO: Add admin permission check
    card_type = db.query(CardType).filter(
        CardType.id == card_type_id
    ).first()
    
    if not card_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card type not found"
        )
    
    for field, value in card_type_update.dict(exclude_unset=True).items():
        setattr(card_type, field, value)
    
    db.commit()
    db.refresh(card_type)
    return card_type
