from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta
from decimal import Decimal
import time
import threading

from app.core.database import get_db, SessionLocal
from app.core.deps import get_current_active_user
from app.models.user import User
from app.models.transaction import Transaction
from app.models.card import Card
from app.schemas.analytics import CategorySpending, SpendingTrend, YearComparison, AIInsight, AnalyticsResponse
from app.services.ai_service import AIService

router = APIRouter()

# --- Lightweight in-memory TTL cache (15s default) ---
class TtlCache:
    def __init__(self, ttl_seconds: int = 15):
        self.ttl = ttl_seconds
        self.store: Dict[Any, Any] = {}
    def get(self, key):
        item = self.store.get(key)
        if not item:
            return None
        ts, data = item
        if time.time() - ts > self.ttl:
            self.store.pop(key, None)
            return None
        return data
    def set(self, key, data):
        self.store[key] = (time.time(), data)

_category_cache = TtlCache(15)
_trends_cache = TtlCache(15)
_comparison_cache = TtlCache(15)
_insights_cache = TtlCache(15)
_dashboard_cache = TtlCache(15)

# Background warmer for insights cache (non-blocking)
def _warm_insights_cache_blocking(user_id):
    try:
        db = SessionLocal()
        # Get recent transactions
        transactions = db.query(Transaction).join(Card).filter(
            Card.user_id == user_id
        ).order_by(Transaction.transaction_date.desc()).limit(100).all()
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
        ai_service = AIService()
        insights_result = ai_service.analyze_spending_patterns(transactions_data)
        insights: List[AIInsight] = []
        if "insights" in insights_result:
            for insight_data in insights_result["insights"]:
                insights.append(AIInsight(
                    type=insight_data.get("type", "suggestion"),
                    title=insight_data.get("title", "Insight"),
                    description=insight_data.get("description", ""),
                    category=insight_data.get("category", "general"),
                    confidence=insight_data.get("confidence", 0.5)
                ))
        _insights_cache.set((user_id,), insights)
    except Exception:
        # Silently fail; insights will be empty until next request warms again
        pass
    finally:
        try:
            db.close()
        except Exception:
            pass

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
    cache_key = (current_user.id, start_date, end_date, currency)
    cached = _category_cache.get(cache_key)
    if cached is not None:
        return cached
    result = _get_category_spending_internal(db, current_user.id, start_date, end_date, currency)
    _category_cache.set(cache_key, result)
    return result

@router.get("/trends", response_model=List[SpendingTrend])
async def get_spending_trends(
    months: int = Query(12, ge=1, le=24),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get historical spending trends"""
    cache_key = (current_user.id, months)
    cached = _trends_cache.get(cache_key)
    if cached is not None:
        return cached

    start_date = (date.today().replace(day=1) - timedelta(days=months * 31)).replace(day=1)

    # Use date_trunc for Postgres; fallback to strftime for SQLite by dialect detection if needed
    # Here we avoid dialect branching and format in SQL: to_char(date_trunc('month', ...), 'YYYY-MM')
    month_expr = func.to_char(func.date_trunc('month', Transaction.transaction_date), 'YYYY-MM')

    results = db.query(
        month_expr.label('month'),
        func.sum(Transaction.amount).label('total_amount')
    ).join(Card).filter(
        Card.user_id == current_user.id,
        Transaction.transaction_date >= start_date
    ).group_by(
        month_expr
    ).order_by('month').all()

    payload = [
        SpendingTrend(
            month=result.month,
            amount=result.total_amount or Decimal('0')
        )
        for result in results
    ]
    _trends_cache.set(cache_key, payload)
    return payload

@router.get("/comparison", response_model=YearComparison)
async def get_year_comparison(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get year-over-year spending comparison"""
    cache_key = (current_user.id,)
    cached = _comparison_cache.get(cache_key)
    if cached is not None:
        return cached

    current_year = datetime.now().year
    previous_year = current_year - 1

    # Optimize with explicit date ranges (uses index on transaction_date)
    cur_start = date(current_year, 1, 1)
    cur_end = date(current_year, 12, 31)
    prev_start = date(previous_year, 1, 1)
    prev_end = date(previous_year, 12, 31)

    current_spending = db.query(func.sum(Transaction.amount)).join(Card).filter(
        Card.user_id == current_user.id,
        Transaction.transaction_date >= cur_start,
        Transaction.transaction_date <= cur_end
    ).scalar() or Decimal('0')

    previous_spending = db.query(func.sum(Transaction.amount)).join(Card).filter(
        Card.user_id == current_user.id,
        Transaction.transaction_date >= prev_start,
        Transaction.transaction_date <= prev_end
    ).scalar() or Decimal('0')

    if previous_spending > 0:
        percentage_change = float((current_spending - previous_spending) / previous_spending * 100)
    else:
        percentage_change = 0.0

    result = YearComparison(
        current_year=current_year,
        previous_year=previous_year,
        current_amount=current_spending,
        previous_amount=previous_spending,
        percentage_change=percentage_change
    )
    _comparison_cache.set(cache_key, result)
    return result

@router.get("/insights", response_model=List[AIInsight])
async def get_ai_insights(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get AI-powered spending insights"""
    cache_key = (current_user.id,)
    cached = _insights_cache.get(cache_key)
    if cached is not None:
        return cached

    # Compute synchronously first time when called directly
    transactions = db.query(Transaction).join(Card).filter(
        Card.user_id == current_user.id
    ).order_by(Transaction.transaction_date.desc()).limit(100).all()

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

    ai_service = AIService()
    insights_result = ai_service.analyze_spending_patterns(transactions_data)

    insights: List[AIInsight] = []
    if "insights" in insights_result:
        for insight_data in insights_result["insights"]:
            insights.append(AIInsight(
                type=insight_data.get("type", "suggestion"),
                title=insight_data.get("title", "Insight"),
                description=insight_data.get("description", ""),
                category=insight_data.get("category", "general"),
                confidence=insight_data.get("confidence", 0.5)
            ))
    _insights_cache.set(cache_key, insights)
    return insights

@router.get("/", response_model=AnalyticsResponse)
async def get_analytics_dashboard(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get complete analytics dashboard data"""
    cache_key = (current_user.id,)
    cached = _dashboard_cache.get(cache_key)
    if cached is not None:
        return cached

    # Category spending current month
    current_month = date.today().replace(day=1)
    category_spending = _get_category_spending_internal(
        db=db,
        user_id=current_user.id,
        start_date=current_month,
        currency=None
    )

    trends = await get_spending_trends(
        months=12,
        current_user=current_user,
        db=db
    )

    year_comparison = await get_year_comparison(
        current_user=current_user,
        db=db
    )

    # Serve insights from cache if present; otherwise return quickly and warm in background
    insights_cached = _insights_cache.get((current_user.id,))
    if insights_cached is None:
        # Fire-and-forget warm-up
        threading.Thread(target=_warm_insights_cache_blocking, args=(current_user.id,), daemon=True).start()
        insights = []
    else:
        insights = insights_cached

    payload = AnalyticsResponse(
        category_spending=category_spending,
        trends=trends,
        year_comparison=year_comparison,
        insights=insights
    )
    _dashboard_cache.set(cache_key, payload)
    return payload
