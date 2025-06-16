from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List
from datetime import date, datetime
from decimal import Decimal
import uuid

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.models.budget import Budget
from app.models.transaction import Transaction
from app.models.card import Card
from app.schemas.budget import BudgetCreate, BudgetUpdate, Budget as BudgetSchema, BudgetAlert

router = APIRouter()

@router.get("/", response_model=List[BudgetSchema])
async def get_budgets(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all budgets for the current user"""
    budgets = db.query(Budget).filter(Budget.user_id == current_user.id).all()
    return budgets

@router.post("/", response_model=BudgetSchema)
async def create_budget(
    budget_create: BudgetCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new budget"""
    # Check if budget already exists for this category and month
    existing_budget = db.query(Budget).filter(
        Budget.user_id == current_user.id,
        Budget.category == budget_create.category,
        Budget.month == budget_create.month
    ).first()
    
    if existing_budget:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Budget already exists for this category and month"
        )
    
    budget = Budget(**budget_create.dict(), user_id=current_user.id)
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget

@router.get("/alerts", response_model=List[BudgetAlert])
async def get_budget_alerts(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get budget alerts for overspending"""
    current_month = date.today().replace(day=1)
    
    budgets = db.query(Budget).filter(
        Budget.user_id == current_user.id,
        Budget.month == current_month
    ).all()
    
    alerts = []
    
    for budget in budgets:
        # Calculate current spending for this category
        spending = db.query(func.sum(Transaction.amount)).join(Card).filter(
            Card.user_id == current_user.id,
            Transaction.category == budget.category,
            func.extract('year', Transaction.transaction_date) == current_month.year,
            func.extract('month', Transaction.transaction_date) == current_month.month
        ).scalar() or Decimal('0')
        
        percentage_used = float(spending) / float(budget.limit_amount) * 100
        
        # Generate alerts for 90% and 100% thresholds
        if percentage_used >= 100:
            alerts.append(BudgetAlert(
                budget=budget,
                current_spending=spending,
                percentage_used=percentage_used,
                alert_type="exceeded"
            ))
        elif percentage_used >= 90:
            alerts.append(BudgetAlert(
                budget=budget,
                current_spending=spending,
                percentage_used=percentage_used,
                alert_type="warning"
            ))
    
    return alerts

@router.get("/{budget_id}", response_model=BudgetSchema)
async def get_budget(
    budget_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific budget"""
    budget = db.query(Budget).filter(
        Budget.id == budget_id,
        Budget.user_id == current_user.id
    ).first()
    
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )

    return budget

@router.put("/{budget_id}", response_model=BudgetSchema)
async def update_budget(
    budget_id: uuid.UUID,
    budget_update: BudgetUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a budget"""
    budget = db.query(Budget).filter(
        Budget.id == budget_id,
        Budget.user_id == current_user.id
    ).first()
    
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )
    
    update_data = budget_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(budget, field, value)
    
    db.commit()
    db.refresh(budget)
    return budget

@router.delete("/{budget_id}")
async def delete_budget(
    budget_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a budget"""
    budget = db.query(Budget).filter(
        Budget.id == budget_id,
        Budget.user_id == current_user.id
    ).first()
    
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )
    
    db.delete(budget)
    db.commit()
    return {"message": "Budget deleted successfully"}
