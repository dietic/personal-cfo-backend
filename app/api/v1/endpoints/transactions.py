from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
import uuid

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.models.transaction import Transaction
from app.models.card import Card
from app.schemas.transaction import TransactionCreate, TransactionUpdate, Transaction as TransactionSchema
from app.services.ai_service import AIService

router = APIRouter()

@router.get("/", response_model=List[TransactionSchema])
async def get_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    card_id: Optional[uuid.UUID] = None,
    category: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get transactions with filters"""
    query = db.query(Transaction).join(Card).filter(Card.user_id == current_user.id)
    
    if card_id:
        query = query.filter(Transaction.card_id == card_id)
    if category:
        query = query.filter(Transaction.category == category)
    if start_date:
        query = query.filter(Transaction.transaction_date >= start_date)
    if end_date:
        query = query.filter(Transaction.transaction_date <= end_date)
    
    transactions = query.offset(skip).limit(limit).all()
    return transactions

@router.post("/", response_model=TransactionSchema)
async def create_transaction(
    transaction_create: TransactionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new transaction"""
    # Verify card belongs to user
    card = db.query(Card).filter(
        Card.id == transaction_create.card_id,
        Card.user_id == current_user.id
    ).first()
    
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    
    # Auto-categorize if no category provided
    if not transaction_create.category:
        ai_service = AIService()
        ai_result = ai_service.categorize_transaction(
            transaction_create.merchant,
            float(transaction_create.amount),
            transaction_create.description or ""
        )
        transaction_create.category = ai_result["category"]
    
    transaction = Transaction(**transaction_create.dict())
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction

@router.get("/{transaction_id}", response_model=TransactionSchema)
async def get_transaction(
    transaction_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific transaction"""
    transaction = db.query(Transaction).join(Card).filter(
        Transaction.id == transaction_id,
        Card.user_id == current_user.id
    ).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    return transaction

@router.put("/{transaction_id}", response_model=TransactionSchema)
async def update_transaction(
    transaction_id: uuid.UUID,
    transaction_update: TransactionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a transaction"""
    transaction = db.query(Transaction).join(Card).filter(
        Transaction.id == transaction_id,
        Card.user_id == current_user.id
    ).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    update_data = transaction_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(transaction, field, value)
    
    db.commit()
    db.refresh(transaction)
    return transaction

@router.delete("/{transaction_id}")
async def delete_transaction(
    transaction_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a transaction"""
    transaction = db.query(Transaction).join(Card).filter(
        Transaction.id == transaction_id,
        Card.user_id == current_user.id
    ).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    db.delete(transaction)
    db.commit()
    return {"message": "Transaction deleted successfully"}
