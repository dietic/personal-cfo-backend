from pydantic import BaseModel
from typing import Dict, List, Any
from decimal import Decimal
from datetime import date

class CategorySpending(BaseModel):
    category: str
    amount: Decimal
    transaction_count: int
    currency: str

class SpendingTrend(BaseModel):
    month: str
    amount: Decimal

class MonthlyCategoryBreakdown(BaseModel):
    month: str
    categories: Dict[str, Dict[str, str]]  # category_name -> {currency -> amount}

class YearComparison(BaseModel):
    current_year: int
    previous_year: int
    current_amount: Decimal
    previous_amount: Decimal
    percentage_change: float


class AnalyticsResponse(BaseModel):
    category_spending: List[CategorySpending]
    trends: List[SpendingTrend]
    year_comparison: YearComparison
