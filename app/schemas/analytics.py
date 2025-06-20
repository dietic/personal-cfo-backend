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

class YearComparison(BaseModel):
    current_year: int
    previous_year: int
    current_amount: Decimal
    previous_amount: Decimal
    percentage_change: float

class AIInsight(BaseModel):
    type: str  # "overspending", "suggestion", "anomaly"
    title: str
    description: str
    category: str
    confidence: float

class AnalyticsResponse(BaseModel):
    category_spending: List[CategorySpending]
    trends: List[SpendingTrend]
    year_comparison: YearComparison
    insights: List[AIInsight]
