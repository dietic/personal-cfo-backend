from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
import uuid

class BillingInfo(BaseModel):
    user_id: uuid.UUID
    subscription_plan: str = Field(..., description="Current subscription plan (free, pro, premium)")
    subscription_status: str = Field(..., description="Subscription status (active, cancelled, past_due)")
    billing_cycle: str = Field(..., description="Billing cycle (monthly, yearly)")
    next_billing_date: Optional[date] = Field(None, description="Next billing date")
    monthly_limit: int = Field(..., description="Monthly transaction limit")
    current_usage: int = Field(..., description="Current month usage")

class BillingInfoUpdate(BaseModel):
    subscription_plan: Optional[str] = Field(None, description="Subscription plan to change to")
    billing_cycle: Optional[str] = Field(None, description="Billing cycle (monthly, yearly)")
    next_billing_date: Optional[date] = Field(None, description="Next billing date")

class UsageStats(BaseModel):
    user_id: uuid.UUID
    period_start: date
    period_end: date
    transactions_processed: int = Field(..., description="Number of transactions processed this period")
    statements_uploaded: int = Field(..., description="Number of statements uploaded this period")
    ai_analyses_used: int = Field(..., description="Number of AI analyses used this period")
    total_transactions: int = Field(..., description="Total transactions ever")
    total_statements: int = Field(..., description="Total statements ever")
    monthly_limit: int = Field(..., description="Monthly limit for current plan")
    percentage_used: float = Field(..., description="Percentage of monthly limit used")

class BillingHistory(BaseModel):
    id: str
    user_id: uuid.UUID
    period_start: date
    period_end: date
    amount: Decimal
    currency: str = "USD"
    status: str = Field(..., description="Payment status (paid, pending, failed)")
    invoice_url: Optional[str] = Field(None, description="URL to download invoice")
    created_at: datetime

    class Config:
        from_attributes = True

class PaymentMethodCreate(BaseModel):
    type: str = Field(..., description="Payment method type (card, paypal, bank)")
    expires_at: Optional[date] = Field(None, description="Expiration date for cards")

class PaymentMethod(BaseModel):
    id: str
    user_id: uuid.UUID
    type: str = Field(..., description="Payment method type (card, paypal, bank)")
    last_four: str = Field(..., description="Last 4 digits/characters")
    expires_at: Optional[date] = Field(None, description="Expiration date")
    is_default: bool = Field(False, description="Whether this is the default payment method")
    created_at: datetime

    class Config:
        from_attributes = True

class InvoiceResponse(BaseModel):
    id: str
    user_id: uuid.UUID
    invoice_number: str
    amount: Decimal
    currency: str = "USD"
    status: str = Field(..., description="Invoice status (paid, pending, failed)")
    period_start: date
    period_end: date
    download_url: Optional[str] = Field(None, description="URL to download PDF")
    created_at: datetime

    class Config:
        from_attributes = True

class SubscriptionPlan(BaseModel):
    name: str = Field(..., description="Plan name (free, pro, premium)")
    price: Decimal = Field(..., description="Monthly price")
    currency: str = "USD"
    features: List[str] = Field(..., description="List of plan features")
    transaction_limit: int = Field(..., description="Monthly transaction limit")
    statement_limit: int = Field(..., description="Monthly statement limit")
    ai_analysis_limit: int = Field(..., description="Monthly AI analysis limit")
    support_level: str = Field(..., description="Support level (community, email, priority)")

class PlanComparison(BaseModel):
    plans: List[SubscriptionPlan]
