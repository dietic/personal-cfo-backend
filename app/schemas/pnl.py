from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import date
from decimal import Decimal
from enum import Enum

class TransactionType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"

class PnLCategorySummary(BaseModel):
    """Summary of a category in P&L"""
    category: str
    amount_base: Decimal = Field(..., description="Amount in base currency")
    percentage: float = Field(..., description="Percentage of total income/expense")
    transaction_count: int = Field(..., description="Number of transactions in this category")
    trend_vs_previous: Optional[float] = Field(None, description="Trend vs previous period in percentage")

class PnLSummary(BaseModel):
    """Complete P&L summary"""
    period_start: date
    period_end: date
    base_currency: str
    
    # Totals
    total_income: Decimal = Field(..., description="Total income in base currency")
    total_expenses: Decimal = Field(..., description="Total expenses in base currency")
    net_amount: Decimal = Field(..., description="Net amount (income - expenses) in base currency")
    savings_rate: float = Field(..., description="Savings rate as percentage (net / income)")
    
    # Category breakdowns
    income_by_category: List[PnLCategorySummary] = Field(..., description="Income breakdown by source/type")
    expenses_by_category: List[PnLCategorySummary] = Field(..., description="Expenses breakdown by category")
    
    # Exchange rate information
    exchange_rate_policy: str = Field(..., description="Exchange rate policy used")
    average_exchange_rate: Optional[float] = Field(None, description="Average exchange rate used for conversions")
    
    # Metadata
    is_profitable: bool = Field(..., description="Whether the period was profitable (net >= 0)")
    has_unclassified_income: bool = Field(..., description="Whether there are unclassified income transactions")
    unclassified_income_count: int = Field(0, description="Number of unclassified income transactions")

class PnLRequest(BaseModel):
    """Request parameters for P&L calculation"""
    start_date: Optional[date] = Field(None, description="Start date of period (default: current month start)")
    end_date: Optional[date] = Field(None, description="End date of period (default: today)")
    base_currency: Optional[str] = Field(None, description="Base currency for conversion (default: user's base currency)")
    include_net_by_category: bool = Field(False, description="Whether to include net by category calculation")

class PnLExportFormat(str, Enum):
    CSV = "csv"
    PDF = "pdf"

class PnLExportRequest(PnLRequest):
    """Request for P&L export"""
    format: PnLExportFormat = Field(PnLExportFormat.CSV, description="Export format")

class PnLTransaction(BaseModel):
    """Transaction details for P&L"""
    id: str
    date: date
    description: str
    amount_original: Decimal
    currency_original: str
    amount_base: Decimal
    category: str
    type: TransactionType
    merchant: str