from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date
from decimal import Decimal
import uuid

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.schemas.billing import (
    BillingInfo,
    BillingInfoUpdate,
    UsageStats,
    BillingHistory,
    PaymentMethod,
    PaymentMethodCreate,
    InvoiceResponse
)

router = APIRouter()

@router.get("/info", response_model=BillingInfo)
async def get_billing_info(
    current_user: User = Depends(get_current_active_user)
):
    """Get user billing information"""
    # For now, return basic info. In production, this would connect to a billing provider
    return BillingInfo(
        user_id=current_user.id,
        subscription_plan="free",
        subscription_status="active",
        billing_cycle="monthly",
        next_billing_date=None,
        monthly_limit=100,  # transactions per month for free plan
        current_usage=0
    )

@router.put("/info", response_model=BillingInfo)
async def update_billing_info(
    billing_update: BillingInfoUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update billing information"""
    # In production, this would update billing provider information
    # For now, return updated mock data
    return BillingInfo(
        user_id=current_user.id,
        subscription_plan=billing_update.subscription_plan or "free",
        subscription_status="active",
        billing_cycle=billing_update.billing_cycle or "monthly",
        next_billing_date=billing_update.next_billing_date,
        monthly_limit=500 if billing_update.subscription_plan == "pro" else 100,
        current_usage=0
    )

@router.get("/usage", response_model=UsageStats)
async def get_usage_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current usage statistics"""
    from app.models.transaction import Transaction
    from app.models.card import Card
    from app.models.statement import Statement
    from datetime import datetime, timedelta
    
    # Get current month usage
    start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Count transactions this month
    transactions_this_month = db.query(Transaction).join(Card).filter(
        Card.user_id == current_user.id,
        Transaction.created_at >= start_of_month
    ).count()
    
    # Count statements this month
    statements_this_month = db.query(Statement).filter(
        Statement.user_id == current_user.id,
        Statement.created_at >= start_of_month
    ).count()
    
    # Get total counts
    total_transactions = db.query(Transaction).join(Card).filter(
        Card.user_id == current_user.id
    ).count()
    
    total_statements = db.query(Statement).filter(
        Statement.user_id == current_user.id
    ).count()
    
    return UsageStats(
        user_id=current_user.id,
        period_start=start_of_month.date(),
        period_end=datetime.now().date(),
        transactions_processed=transactions_this_month,
        statements_uploaded=statements_this_month,
        ai_analyses_used=statements_this_month,  # Each statement uses AI
        total_transactions=total_transactions,
        total_statements=total_statements,
        monthly_limit=100,  # Free plan limit
        percentage_used=(transactions_this_month / 100) * 100 if transactions_this_month <= 100 else 100
    )

@router.get("/history", response_model=List[BillingHistory])
async def get_billing_history(
    months: int = 12,
    current_user: User = Depends(get_current_active_user)
):
    """Get billing history"""
    # Mock billing history for demonstration
    # In production, this would fetch from billing provider
    history = []
    for i in range(min(months, 6)):  # Return up to 6 months of mock data
        month_date = datetime.now().replace(day=1) - timedelta(days=30 * i)
        history.append(BillingHistory(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            period_start=month_date.date(),
            period_end=(month_date.replace(day=28)).date(),
            amount=Decimal('0.00'),  # Free plan
            currency="USD",
            status="paid",
            invoice_url=None,
            created_at=month_date
        ))
    
    return history

@router.get("/payment-methods", response_model=List[PaymentMethod])
async def get_payment_methods(
    current_user: User = Depends(get_current_active_user)
):
    """Get user payment methods"""
    # Mock payment methods for demonstration
    # In production, this would fetch from payment provider
    return []

@router.post("/payment-methods", response_model=PaymentMethod)
async def add_payment_method(
    payment_method: PaymentMethodCreate,
    current_user: User = Depends(get_current_active_user)
):
    """Add a new payment method"""
    # In production, this would integrate with Stripe/PayPal/etc
    return PaymentMethod(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        type=payment_method.type,
        last_four="****",
        expires_at=payment_method.expires_at,
        is_default=True,
        created_at=datetime.now()
    )

@router.delete("/payment-methods/{method_id}")
async def remove_payment_method(
    method_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Remove a payment method"""
    # In production, this would remove from payment provider
    return {"message": "Payment method removed successfully"}

@router.get("/invoices", response_model=List[InvoiceResponse])
async def get_invoices(
    current_user: User = Depends(get_current_active_user)
):
    """Get user invoices"""
    # Mock invoices for free plan users
    return []

@router.get("/invoices/{invoice_id}")
async def download_invoice(
    invoice_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Download invoice PDF"""
    # In production, this would generate/return actual invoice
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Invoice not found"
    )

@router.post("/upgrade")
async def upgrade_plan(
    plan: str,
    current_user: User = Depends(get_current_active_user)
):
    """Upgrade subscription plan"""
    if plan not in ["pro", "premium"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid plan selected"
        )
    
    # In production, this would handle payment processing
    return {
        "message": f"Successfully upgraded to {plan} plan",
        "plan": plan,
        "status": "active"
    }

@router.post("/cancel")
async def cancel_subscription(
    current_user: User = Depends(get_current_active_user)
):
    """Cancel subscription"""
    # In production, this would cancel with billing provider
    return {
        "message": "Subscription cancelled successfully",
        "plan": "free",
        "status": "cancelled"
    }
