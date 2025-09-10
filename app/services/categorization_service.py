from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional, Tuple
import json
import uuid
import logging

from app.models.transaction import Transaction
from app.models.category import Category
from app.services.category_service import CategoryService
from app.services.ai_service import AIService
from app.schemas.category import CategoryKeywordMatch

logger = logging.getLogger(__name__)


class CategorizationResult:
    def __init__(self):
        self.total_transactions = 0
        self.ai_categorized = 0
        self.keyword_categorized = 0
        self.uncategorized = 0
        self.categorization_details = []
    
    def add_result(self, transaction_id: uuid.UUID, method: str, category: str, confidence: float):
        self.categorization_details.append({
            "transaction_id": str(transaction_id),
            "method": method,
            "category": category,
            "confidence": confidence
        })
        
        if method == "ai":
            self.ai_categorized += 1
        elif method == "keyword":
            self.keyword_categorized += 1
        else:
            self.uncategorized += 1


class CategorizationService:
    
    @staticmethod
    def categorize_transactions(
        db: Session, 
        user_id: uuid.UUID, 
        transactions: List[Transaction],
        use_ai: bool = True,
        use_keywords: bool = True,
        ai_confidence_threshold: float = 0.7,
        keyword_confidence_threshold: float = 0.6
    ) -> CategorizationResult:
        """
        Categorize a list of transactions using multiple methods.
        Priority: Keywords (if high confidence) > AI > Keywords (if low confidence) > Uncategorized
        """
        result = CategorizationResult()
        result.total_transactions = len(transactions)
        
        # Get user categories for keyword matching
        user_categories = CategoryService.get_user_categories(db, user_id) if use_keywords else []
        
        # Prepare batch for AI categorization if enabled
        ai_service = AIService() if use_ai else None
        uncategorized_transactions = []
        
        for transaction in transactions:
            categorized = False
            
            # Skip if already categorized
            if transaction.category:
                result.add_result(transaction.id, "existing", transaction.category, 1.0)
                continue
            
            # Try keyword-based categorization first (high confidence)
            if use_keywords and not categorized:
                keyword_match = CategoryService.categorize_by_keywords(
                    db, user_id, transaction.merchant, transaction.description or ""
                )
                
                if keyword_match and keyword_match.confidence >= keyword_confidence_threshold:
                    transaction.category = keyword_match.category_name
                    transaction.ai_confidence = keyword_match.confidence
                    result.add_result(
                        transaction.id, 
                        "keyword", 
                        keyword_match.category_name, 
                        keyword_match.confidence
                    )
                    categorized = True
                    logger.info(f"Keyword categorized: {transaction.merchant} -> {keyword_match.category_name} (confidence: {keyword_match.confidence})")
            
            # If not categorized by keywords, add to AI batch
            if not categorized and use_ai:
                uncategorized_transactions.append(transaction)
        
        # Process remaining transactions with AI
        if uncategorized_transactions and ai_service:
            try:
                ai_results = CategorizationService._categorize_with_ai(
                    ai_service, uncategorized_transactions, user_categories
                )
                
                for transaction, ai_result in zip(uncategorized_transactions, ai_results):
                    if ai_result and ai_result.get('confidence', 0) >= ai_confidence_threshold:
                        transaction.category = ai_result['category']
                        transaction.ai_confidence = ai_result['confidence']
                        result.add_result(
                            transaction.id,
                            "ai",
                            ai_result['category'],
                            ai_result['confidence']
                        )
                        logger.info(f"AI categorized: {transaction.merchant} -> {ai_result['category']} (confidence: {ai_result['confidence']})")
                    else:
                        # Try low-confidence keyword matching as fallback
                        if use_keywords:
                            keyword_match = CategoryService.categorize_by_keywords(
                                db, user_id, transaction.merchant, transaction.description or ""
                            )
                            
                            if keyword_match and keyword_match.confidence > 0:
                                transaction.category = keyword_match.category_name
                                transaction.ai_confidence = keyword_match.confidence
                                result.add_result(
                                    transaction.id,
                                    "keyword",
                                    keyword_match.category_name,
                                    keyword_match.confidence
                                )
                                logger.info(f"Fallback keyword categorized: {transaction.merchant} -> {keyword_match.category_name}")
                            else:
                                result.add_result(transaction.id, "uncategorized", "Other", 0.0)
                        else:
                            result.add_result(transaction.id, "uncategorized", "Other", 0.0)
                            
            except Exception as e:
                logger.error(f"AI categorization failed: {str(e)}")
                # Fallback to keyword categorization for all remaining transactions
                for transaction in uncategorized_transactions:
                    if use_keywords:
                        keyword_match = CategoryService.categorize_by_keywords(
                            db, user_id, transaction.merchant, transaction.description or ""
                        )
                        
                        if keyword_match:
                            transaction.category = keyword_match.category_name
                            transaction.ai_confidence = keyword_match.confidence
                            result.add_result(
                                transaction.id,
                                "keyword",
                                keyword_match.category_name,
                                keyword_match.confidence
                            )
                        else:
                            result.add_result(transaction.id, "uncategorized", "Other", 0.0)
                    else:
                        result.add_result(transaction.id, "uncategorized", "Other", 0.0)
        
        # Commit all categorization changes
        try:
            db.commit()
            logger.info(f"Categorization completed: {result.ai_categorized} AI, {result.keyword_categorized} keyword, {result.uncategorized} uncategorized")
            
            # Learn from categorized transactions to build merchant registry with categories
            from app.services.merchant_service import MerchantService
            for transaction in transactions:
                try:
                    MerchantService.learn_from_transaction(
                        db=db,
                        user_id=user_id,
                        raw_merchant=transaction.description or "",  # Original description from statement
                        standardized_merchant=transaction.merchant,  # AI-standardized merchant name
                        category=transaction.category  # Now we have the category
                    )
                except Exception as e:
                    logger.warning(f"Failed to learn from merchant {transaction.merchant}: {str(e)}")
                    
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to commit categorization changes: {str(e)}")
            raise
        
        return result
    
    @staticmethod
    def _categorize_with_ai(
        ai_service: AIService, 
        transactions: List[Transaction], 
        user_categories: List[Category]
    ) -> List[Optional[Dict[str, Any]]]:
        """Use AI service to categorize transactions"""
        
        # Prepare category names for AI
        category_names = [cat.name for cat in user_categories]
        if not category_names:
            # Fallback to default categories if user has none
            category_names = ["Food & Dining", "Transportation", "Shopping", "Entertainment", 
                            "Utilities", "Healthcare", "Housing", "Other"]
        
        # Prepare transaction data for AI
        transaction_data = []
        for transaction in transactions:
            transaction_data.append({
                "merchant": transaction.merchant,
                "amount": float(transaction.amount),
                "description": transaction.description or "",
                "date": transaction.transaction_date.isoformat()
            })
        
        try:
            # Call AI service to categorize batch
            ai_results = ai_service.categorize_transactions_batch(
                transactions=transaction_data,
                available_categories=category_names
            )
            
            return ai_results
            
        except Exception as e:
            logger.error(f"AI categorization error: {str(e)}")
            return [None] * len(transactions)
    
    @staticmethod
    def recategorize_transaction(
        db: Session,
        user_id: uuid.UUID,
        transaction_id: uuid.UUID,
        new_category: str,
        confidence: float = 1.0
    ) -> Transaction:
        """Manually recategorize a single transaction"""
        
        transaction = db.query(Transaction).join(
            Transaction.card
        ).filter(
            Transaction.id == transaction_id,
            Transaction.card.has(user_id=user_id)
        ).first()
        
        if not transaction:
            raise ValueError("Transaction not found")
        
        # Verify category exists for user
        category = db.query(Category).filter(
            Category.user_id == user_id,
            Category.name == new_category,
            Category.is_active == True
        ).first()
        
        if not category:
            raise ValueError(f"Category '{new_category}' not found")
        
        transaction.category = new_category
        transaction.ai_confidence = confidence
        
        db.commit()
        db.refresh(transaction)
        
        logger.info(f"Transaction {transaction_id} recategorized to {new_category}")
        return transaction
    
