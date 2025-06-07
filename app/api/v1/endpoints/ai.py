from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.models.transaction import Transaction
from app.models.card import Card
from app.services.ai_service import AIService

router = APIRouter()

@router.post("/categorize")
async def categorize_transaction(
    merchant: str,
    amount: float,
    description: str = "",
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Categorize a transaction using AI"""
    ai_service = AIService()
    result = ai_service.categorize_transaction(merchant, amount, description)
    
    return {
        "category": result["category"],
        "confidence": result["confidence"],
        "reasoning": result["reasoning"]
    }

@router.post("/analyze-spending")
async def analyze_spending_patterns(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Analyze spending patterns for the user"""
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
    
    ai_service = AIService()
    result = ai_service.analyze_spending_patterns(transactions_data)
    
    return result

@router.post("/detect-anomalies")
async def detect_transaction_anomalies(
    merchant: str,
    amount: float,
    category: str,
    description: str = "",
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Detect if a transaction is anomalous based on user history"""
    # Get user's transaction history
    transactions = db.query(Transaction).join(Card).filter(
        Card.user_id == current_user.id
    ).order_by(Transaction.transaction_date.desc()).limit(50).all()
    
    # Convert to format for AI analysis
    user_history = [
        {
            "merchant": tx.merchant,
            "amount": float(tx.amount),
            "category": tx.category,
            "date": tx.transaction_date.isoformat(),
            "description": tx.description
        }
        for tx in transactions
    ]
    
    # New transaction data
    transaction_data = {
        "merchant": merchant,
        "amount": amount,
        "category": category,
        "description": description
    }
    
    ai_service = AIService()
    result = ai_service.detect_anomalies(transaction_data, user_history)
    
    return result
