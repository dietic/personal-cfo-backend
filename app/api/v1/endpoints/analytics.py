from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import List, Dict, Any, Optional
from datetime import date, datetime
from decimal import Decimal

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.models.transaction import Transaction
from app.models.card import Card
from app.schemas.analytics import CategorySpending, SpendingTrend, YearComparison, AIInsight, AnalyticsResponse
from app.services.ai_service import AIService

router = APIRouter()

def _get_category_spending_internal(
    db: Session,
    user_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    currency: Optional[str] = None
) -> List[CategorySpending]:
    """Internal function to get category spending"""
    query = db.query(
        Transaction.category,
        Transaction.currency,
        func.sum(Transaction.amount).label('total_amount'),
        func.count(Transaction.id).label('transaction_count')
    ).join(Card).filter(Card.user_id == user_id)
    
    if start_date:
        query = query.filter(Transaction.transaction_date >= start_date)
    if end_date:
        query = query.filter(Transaction.transaction_date <= end_date)
    if currency:
        query = query.filter(Transaction.currency == currency)
    
    results = query.group_by(Transaction.category, Transaction.currency).all()
    
    return [
        CategorySpending(
            category=result.category or "uncategorized",
            amount=result.total_amount,
            transaction_count=result.transaction_count,
            currency=result.currency
        )
        for result in results
    ]

@router.get("/category", response_model=List[CategorySpending])
async def get_category_spending(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    currency: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get spending per category, optionally filtered by currency"""
    return _get_category_spending_internal(db, current_user.id, start_date, end_date, currency)

@router.get("/trends", response_model=List[SpendingTrend])
async def get_spending_trends(
    months: int = Query(12, ge=1, le=24),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get historical spending trends"""
    results = db.query(
        func.strftime('%Y-%m', Transaction.transaction_date).label('month'),
        func.sum(Transaction.amount).label('total_amount')
    ).join(Card).filter(
        Card.user_id == current_user.id,
        Transaction.transaction_date >= func.date('now', f'-{months} months')
    ).group_by(
        func.strftime('%Y-%m', Transaction.transaction_date)
    ).order_by('month').all()
    
    return [
        SpendingTrend(
            month=result.month,
            amount=result.total_amount or Decimal('0')
        )
        for result in results
    ]

@router.get("/comparison", response_model=YearComparison)
async def get_year_comparison(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get year-over-year spending comparison"""
    current_year = datetime.now().year
    previous_year = current_year - 1
    
    # Current year spending
    current_spending = db.query(func.sum(Transaction.amount)).join(Card).filter(
        Card.user_id == current_user.id,
        extract('year', Transaction.transaction_date) == current_year
    ).scalar() or Decimal('0')
    
    # Previous year spending
    previous_spending = db.query(func.sum(Transaction.amount)).join(Card).filter(
        Card.user_id == current_user.id,
        extract('year', Transaction.transaction_date) == previous_year
    ).scalar() or Decimal('0')
    
    # Calculate percentage change
    if previous_spending > 0:
        percentage_change = float((current_spending - previous_spending) / previous_spending * 100)
    else:
        percentage_change = 0.0
    
    return YearComparison(
        current_year=current_year,
        previous_year=previous_year,
        current_amount=current_spending,
        previous_amount=previous_spending,
        percentage_change=percentage_change
    )

@router.get("/insights", response_model=List[AIInsight])
async def get_ai_insights(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get AI-powered spending insights"""
    # Get recent transactions
    transactions = db.query(Transaction).join(Card).filter(
        Card.user_id == current_user.id
    ).order_by(Transaction.transaction_date.desc()).limit(100).all()
    
    # Convert to format for AI analysis
    transactions_data = [
        {
            "merchant": tx.merchant,
            "amount": float(tx.amount),
            "category": tx.category,
            "date": tx.transaction_date.isoformat(),
            "description": tx.description
        }
        for tx in transactions
    ]
    
    # Get AI insights
    ai_service = AIService()
    insights_result = ai_service.analyze_spending_patterns(transactions_data)
    
    insights = []
    if "insights" in insights_result:
        for insight_data in insights_result["insights"]:
            insights.append(AIInsight(
                type=insight_data.get("type", "suggestion"),
                title=insight_data.get("title", "Insight"),
                description=insight_data.get("description", ""),
                category=insight_data.get("category", "general"),
                confidence=insight_data.get("confidence", 0.5)
            ))
    
    return insights

@router.get("/", response_model=AnalyticsResponse)
async def get_analytics_dashboard(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get complete analytics dashboard data"""
    # Get category spending for current month
    current_month = date.today().replace(day=1)
    category_spending = _get_category_spending_internal(
        db=db,
        user_id=current_user.id,
        start_date=current_month,
        currency=None  # Get all currencies for dashboard overview
    )
    
    # Get trends for last 12 months
    trends = await get_spending_trends(
        months=12,
        current_user=current_user,
        db=db
    )
    
    # Get year comparison
    year_comparison = await get_year_comparison(
        current_user=current_user,
        db=db
    )
    
    # Get AI insights
    insights = await get_ai_insights(
        current_user=current_user,
        db=db
    )
    
    return AnalyticsResponse(
        category_spending=category_spending,
        trends=trends,
        year_comparison=year_comparison,
        insights=insights
    )
