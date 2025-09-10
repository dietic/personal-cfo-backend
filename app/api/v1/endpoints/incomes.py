from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime
import uuid
import logging

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.models.income import Income as IncomeModel
from app.models.transaction import Transaction
from app.models.card import Card
from app.schemas.income import IncomeCreate, IncomeUpdate, Income
from app.services.income_service import IncomeService

router = APIRouter()

def _get_or_create_default_card(db: Session, user_id: uuid.UUID) -> Card:
    """Get user's card or create a default one for income transactions"""
    # Try to find an existing card for this user
    existing_cards = db.query(Card).filter(Card.user_id == user_id).all()
    
    if existing_cards:
        # Use the first available card
        return existing_cards[0]
    
    # Create a default card if none exists
    default_card = Card(
        user_id=user_id,
        card_name="Default Income Card"
    )
    
    db.add(default_card)
    db.commit()
    db.refresh(default_card)
    return default_card


@router.get("/", response_model=List[Income])
async def get_incomes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    is_recurring: Optional[bool] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get incomes with optional filtering"""
    query = db.query(IncomeModel).filter(IncomeModel.user_id == current_user.id)
    
    if start_date:
        query = query.filter(IncomeModel.income_date >= start_date)
    if end_date:
        query = query.filter(IncomeModel.income_date <= end_date)
    if is_recurring is not None:
        query = query.filter(IncomeModel.is_recurring == is_recurring)
    
    incomes = query.order_by(IncomeModel.income_date.desc()).offset(skip).limit(limit).all()
    return incomes

@router.post("/", response_model=Income)
async def create_income(
    income_create: IncomeCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new income record and associated transaction"""
    # Verify that the card belongs to the current user
    card = db.query(Card).filter(
        Card.id == income_create.card_id,
        Card.user_id == current_user.id
    ).first()
    
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found or does not belong to user"
        )
    
    # Set recurring_day from income_date if this is a recurring income
    recurring_day = None
    if income_create.is_recurring:
        recurring_day = income_create.income_date.day
    
    income = IncomeModel(
        user_id=current_user.id,
        card_id=income_create.card_id,
        amount=income_create.amount,
        currency=income_create.currency,
        description=income_create.description,
        source=income_create.source,
        income_date=income_create.income_date,
        is_recurring=income_create.is_recurring,
        recurring_day=recurring_day
    )
    
    # Validate income amount is positive
    income.validate_amount()
    
    db.add(income)
    db.commit()
    db.refresh(income)
    
    logger.info(f"Created income: {income.description} - {income.amount} {income.currency}")
    
    # Create past recurring transactions if this is a recurring income
    if income.is_recurring:
        income_service = IncomeService(db)
        past_count = income_service.create_past_recurring_transactions(income)
        logger.info(f"Created {past_count} past recurring transactions")
    
    # Create associated transaction for the income
    transaction = Transaction(
        card_id=income_create.card_id,
        merchant=income_create.source,
        amount=income_create.amount,
        currency=income_create.currency,
        category="Income",
        transaction_date=income_create.income_date,
        description=f"Income: {income_create.description}"
    )
    
    try:
        db.add(transaction)
        db.commit()
        
        logger.info(f"Created transaction for income: {transaction.merchant} - {transaction.amount} {transaction.currency}")
        
    except Exception as e:
        logger.error(f"Failed to create transaction for income: {e}", exc_info=True)
        db.rollback()
        # Re-raise the exception so the API returns an error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create transaction: {str(e)}"
        )
    
    return income

@router.get("/{income_id}", response_model=Income)
async def get_income(
    income_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific income"""
    income = db.query(IncomeModel).filter(
        IncomeModel.id == income_id,
        IncomeModel.user_id == current_user.id
    ).first()
    
    if not income:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Income not found"
        )
    
    return income

@router.put("/{income_id}", response_model=Income)
async def update_income(
    income_id: uuid.UUID,
    income_update: IncomeUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update an income record"""
    income = db.query(IncomeModel).filter(
        IncomeModel.id == income_id,
        IncomeModel.user_id == current_user.id
    ).first()
    
    if not income:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Income not found"
        )
    
    # If card_id is being updated, verify the new card belongs to the user
    update_data = income_update.dict(exclude_unset=True)
    
    if 'card_id' in update_data:
        card = db.query(Card).filter(
            Card.id == update_data['card_id'],
            Card.user_id == current_user.id
        ).first()
        
        if not card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Card not found or does not belong to user"
            )
    
    # Handle recurring_day logic: if is_recurring is being set to True and income_date exists,
    # automatically set recurring_day from income_date
    if update_data.get('is_recurring') is True:
        if 'income_date' in update_data:
            update_data['recurring_day'] = update_data['income_date'].day
        elif income.income_date:
            update_data['recurring_day'] = income.income_date.day
    elif update_data.get('is_recurring') is False:
        # If turning off recurrence, clear recurring_day
        update_data['recurring_day'] = None
    
    # If income_date is being updated and this is a recurring income, update recurring_day too
    if 'income_date' in update_data and income.is_recurring:
        update_data['recurring_day'] = update_data['income_date'].day
    
    for field, value in update_data.items():
        setattr(income, field, value)
    
    # Validate income amount is positive after update
    income.validate_amount()
    
    db.commit()
    db.refresh(income)
    return income

@router.delete("/{income_id}")
async def delete_income(
    income_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete an income record"""
    income = db.query(IncomeModel).filter(
        IncomeModel.id == income_id,
        IncomeModel.user_id == current_user.id
    ).first()
    
    if not income:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Income not found"
        )
    
    db.delete(income)
    db.commit()
    return {"message": "Income deleted successfully"}

@router.get("/recurring/summary")
async def get_recurring_income_summary(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get summary of recurring incomes"""
    recurring_incomes = db.query(IncomeModel).filter(
        IncomeModel.user_id == current_user.id,
        IncomeModel.is_recurring == True
    ).all()
    
    total_monthly = sum(float(income.amount) for income in recurring_incomes)
    
    return {
        "total_recurring_incomes": len(recurring_incomes),
        "total_monthly_amount": total_monthly,
        "recurring_incomes": [income.to_dict() for income in recurring_incomes]
    }

@router.get("/non-recurring/summary")
async def get_non_recurring_income_summary(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get summary of non-recurring incomes for a given period"""
    query = db.query(IncomeModel).filter(
        IncomeModel.user_id == current_user.id,
        IncomeModel.is_recurring == False
    )
    
    if start_date:
        query = query.filter(IncomeModel.income_date >= start_date)
    if end_date:
        query = query.filter(IncomeModel.income_date <= end_date)
    
    non_recurring_incomes = query.all()
    total_amount = sum(float(income.amount) for income in non_recurring_incomes)
    
    return {
        "total_non_recurring_incomes": len(non_recurring_incomes),
        "total_amount": total_amount,
        "non_recurring_incomes": [income.to_dict() for income in non_recurring_incomes]
    }