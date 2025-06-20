from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
import uuid
from datetime import datetime

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.models.card import Card
from app.models.bank_provider import BankProvider
from app.models.network_provider import NetworkProvider
from app.models.card_type import CardType
from app.schemas.card import CardCreate, CardUpdate, Card as CardSchema

router = APIRouter()

@router.get("/", response_model=List[CardSchema])
async def get_cards(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all cards for the current user with full relationship details.
    
    Using joinedload to fetch all related data in a single query - like getting
    a complete profile instead of just basic info.
    """
    cards = db.query(Card).options(
        joinedload(Card.bank_provider),
        joinedload(Card.network_provider),
        joinedload(Card.card_type)
    ).filter(Card.user_id == current_user.id).all()
    return cards

@router.post("/", response_model=CardSchema)
async def create_card(
    card_create: CardCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new card with full validation of all relationships.
    
    Like registering a new payment method - we need to verify all the
    related entities (bank, network, type) exist before linking them.
    """
    # Validate bank provider exists if provided
    if card_create.bank_provider_id:
        bank_provider = db.query(BankProvider).filter(
            BankProvider.id == card_create.bank_provider_id,
            BankProvider.is_active == True
        ).first()
        
        if not bank_provider:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid bank provider"
            )
    
    # Validate network provider exists if provided
    if card_create.network_provider_id:
        network_provider = db.query(NetworkProvider).filter(
            NetworkProvider.id == card_create.network_provider_id,
            NetworkProvider.is_active == True
        ).first()
        
        if not network_provider:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid network provider"
            )
    
    # Validate card type exists if provided
    if card_create.card_type_id:
        card_type = db.query(CardType).filter(
            CardType.id == card_create.card_type_id,
            CardType.is_active == True
        ).first()
        
        if not card_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid card type"
            )
    
    card_data = card_create.dict()
    card_data.update({
        'user_id': current_user.id,
        'created_at': datetime.utcnow()  # Explicitly set created_at since DB default isn't working
    })
    card = Card(**card_data)
    db.add(card)
    db.commit()
    
    # Refresh with all relationship details
    db.refresh(card)
    card = db.query(Card).options(
        joinedload(Card.bank_provider),
        joinedload(Card.network_provider),
        joinedload(Card.card_type)
    ).filter(Card.id == card.id).first()
    
    return card

@router.get("/{card_id}", response_model=CardSchema)
async def get_card(
    card_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific card by ID with all relationship details"""
    card = db.query(Card).options(
        joinedload(Card.bank_provider),
        joinedload(Card.network_provider),
        joinedload(Card.card_type)
    ).filter(
        Card.id == card_id,
        Card.user_id == current_user.id
    ).first()
    
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    
    return card

@router.put("/{card_id}", response_model=CardSchema)
async def update_card(
    card_id: uuid.UUID,
    card_update: CardUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a card"""
    card = db.query(Card).filter(
        Card.id == card_id,
        Card.user_id == current_user.id
    ).first()
    
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    
    update_data = card_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(card, field, value)
    
    db.commit()
    db.refresh(card)
    return card

@router.delete("/{card_id}")
async def delete_card(
    card_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a card"""
    card = db.query(Card).filter(
        Card.id == card_id,
        Card.user_id == current_user.id
    ).first()
    
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    
    db.delete(card)
    db.commit()
    return {"message": "Card deleted successfully"}
