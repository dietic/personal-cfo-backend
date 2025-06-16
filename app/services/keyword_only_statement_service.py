"""
Pure keyword-based statement processing service.
Replaces AI categorization with deterministic keyword matching.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import json
import uuid
from datetime import datetime
import logging
import PyPDF2
import io

from app.models.statement import Statement
from app.models.transaction import Transaction
from app.models.category import Category
from app.models.card import Card
from app.services.keyword_categorization_service import KeywordCategorizationService
from app.services.pattern_based_statement_service import PatternBasedStatementService
from app.core.exceptions import ValidationError, ProcessingError

logger = logging.getLogger(__name__)


class KeywordOnlyStatementService:
    """Statement processing service that uses pure keyword-based categorization"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.keyword_categorization = KeywordCategorizationService(db_session)
        self.pattern_extractor = PatternBasedStatementService()
    
    def process_statement_keyword_only(
        self, 
        statement_id: uuid.UUID,
        file_content: bytes
    ) -> Dict[str, Any]:
        """
        Process statement using pattern extraction + keyword categorization only.
        No AI is used in this process.
        """
        statement = self.db.query(Statement).filter(Statement.id == statement_id).first()
        if not statement:
            raise ValidationError("Statement not found")
        
        try:
            # Update status
            statement.status = "processing"
            statement.extraction_status = "in_progress"
            self.db.commit()
            
            logger.info(f"Starting keyword-only processing for statement {statement_id}")
            
            # Step 1: Extract transactions using pattern matching (no AI)
            logger.info("Extracting transactions using pattern matching...")
            statement_text = self.pattern_extractor.extract_text_from_pdf(file_content)
            raw_transactions = self.pattern_extractor.extract_transactions_from_statement(statement_text)
            
            if not raw_transactions:
                raise ProcessingError("No transactions found in statement")
            
            logger.info(f"Extracted {len(raw_transactions)} transactions using patterns")
            
            # Step 2: Get user categories for keyword categorization
            user_categories = self.db.query(Category).filter(
                Category.user_id == statement.user_id,
                Category.is_active == True
            ).all()
            
            if not user_categories:
                raise ValidationError("User has no active categories")
            
            # Step 3: Categorize transactions using keywords only
            logger.info("Categorizing transactions using keywords only...")
            categorized_transactions = self.keyword_categorization.categorize_transactions_batch(
                str(statement.user_id), raw_transactions
            )
            
            # Step 4: Get user's cards for transaction creation
            user_cards = self.db.query(Card).filter(Card.user_id == statement.user_id).all()
            if not user_cards:
                raise ValidationError("User has no cards configured")
            
            default_card = user_cards[0]
            
            # Step 5: Create Transaction objects
            created_transactions = []
            for txn_data in categorized_transactions:
                transaction = Transaction(
                    card_id=default_card.id,
                    statement_id=statement.id,
                    merchant=txn_data.get('description', txn_data.get('merchant', '')),
                    amount=txn_data['amount'],
                    currency=txn_data.get('currency', 'USD'),
                    category=txn_data['category'],
                    transaction_date=txn_data['transaction_date'],
                    description=txn_data.get('description', ''),
                    ai_confidence=txn_data['confidence']  # Keyword confidence
                )
                
                self.db.add(transaction)
                created_transactions.append(transaction)
            
            # Step 6: Store processed transactions as JSON
            statement.processed_transactions = json.dumps([
                {
                    "description": txn_data.get('description', ''),
                    "amount": float(txn_data['amount']),
                    "currency": txn_data.get('currency', 'USD'),
                    "category": txn_data['category'],
                    "transaction_date": txn_data['transaction_date'].isoformat() if hasattr(txn_data['transaction_date'], 'isoformat') else str(txn_data['transaction_date']),
                    "confidence": txn_data['confidence'],
                    "categorization_method": txn_data.get('categorization_method', 'keyword'),
                    "matched_keywords": txn_data.get('matched_keywords', [])
                }
                for txn_data in categorized_transactions
            ])
            
            # Step 7: Update statement status
            statement.status = "completed"
            statement.extraction_status = "completed" 
            statement.categorization_status = "completed"
            statement.is_processed = True
            
            self.db.commit()
            
            # Calculate summary statistics
            categorized_count = len([t for t in categorized_transactions if t['category'] != 'Uncategorized'])
            uncategorized_count = len([t for t in categorized_transactions if t['category'] == 'Uncategorized'])
            
            result = {
                "statement_id": str(statement.id),
                "status": "completed",
                "processing_method": "keyword_only",
                "transactions_count": len(created_transactions),
                "categorization_summary": {
                    "total": len(categorized_transactions),
                    "categorized": categorized_count,
                    "uncategorized": uncategorized_count,
                    "keyword_coverage": (categorized_count / len(categorized_transactions)) * 100 if categorized_transactions else 0
                },
                "transactions": [
                    {
                        "id": str(txn.id),
                        "description": txn.description,
                        "amount": float(txn.amount),
                        "currency": txn.currency,
                        "category": txn.category,
                        "transaction_date": txn.transaction_date.isoformat(),
                        "confidence": txn.ai_confidence,
                        "categorization_method": "keyword"
                    }
                    for txn in created_transactions
                ]
            }
            
            logger.info(f"Keyword-only processing completed for statement {statement_id}: {categorized_count} categorized, {uncategorized_count} uncategorized")
            return result
            
        except Exception as e:
            # Rollback and update error status
            self.db.rollback()
            
            statement = self.db.query(Statement).filter(Statement.id == statement_id).first()
            if statement:
                statement.status = "failed"
                statement.error_message = str(e)
                self.db.commit()
            
            logger.error(f"Keyword-only processing failed for statement {statement_id}: {str(e)}")
            raise ProcessingError(f"Failed to process statement: {str(e)}")
    
    def recategorize_statement_transactions(
        self, 
        statement_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Re-categorize all transactions in a statement using current keywords.
        Useful when user has updated their keywords.
        """
        statement = self.db.query(Statement).filter(Statement.id == statement_id).first()
        if not statement:
            raise ValidationError("Statement not found")
        
        # Get all transactions for this statement
        transactions = self.db.query(Transaction).filter(
            Transaction.statement_id == statement_id
        ).all()
        
        if not transactions:
            raise ValidationError("No transactions found for statement")
        
        logger.info(f"Re-categorizing {len(transactions)} transactions for statement {statement_id}")
        
        # Use keyword categorization service
        results = self.keyword_categorization.categorize_database_transactions(
            str(statement.user_id), transactions
        )
        
        # Update statement categorization status
        statement.categorization_status = "completed"
        self.db.commit()
        
        logger.info(f"Re-categorization completed: {results['categorized']} categorized, {results['uncategorized']} uncategorized")
        
        return {
            "statement_id": str(statement_id),
            "recategorization_summary": results,
            "transactions_updated": len(transactions)
        }
    
    def get_statement_keyword_analysis(
        self, 
        statement_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Analyze a statement's transactions to show keyword matching results.
        """
        statement = self.db.query(Statement).filter(Statement.id == statement_id).first()
        if not statement:
            raise ValidationError("Statement not found")
        
        transactions = self.db.query(Transaction).filter(
            Transaction.statement_id == statement_id
        ).all()
        
        analysis = {
            "statement_id": str(statement_id),
            "total_transactions": len(transactions),
            "categorization_breakdown": {
                "keyword_categorized": 0,
                "uncategorized": 0,
                "by_category": {}
            },
            "keyword_matches": [],
            "uncategorized_transactions": []
        }
        
        for transaction in transactions:
            if transaction.category == 'Uncategorized':
                analysis["categorization_breakdown"]["uncategorized"] += 1
                analysis["uncategorized_transactions"].append({
                    "id": str(transaction.id),
                    "merchant": transaction.merchant,
                    "description": transaction.description,
                    "amount": float(transaction.amount)
                })
            else:
                analysis["categorization_breakdown"]["keyword_categorized"] += 1
                
                # Count by category
                category = transaction.category
                if category not in analysis["categorization_breakdown"]["by_category"]:
                    analysis["categorization_breakdown"]["by_category"][category] = 0
                analysis["categorization_breakdown"]["by_category"][category] += 1
                
                # Test current keyword matching for this transaction
                match = self.keyword_categorization.categorize_transaction(
                    str(statement.user_id), 
                    transaction.merchant, 
                    transaction.description or ""
                )
                
                if match:
                    analysis["keyword_matches"].append({
                        "transaction_id": str(transaction.id),
                        "merchant": transaction.merchant,
                        "current_category": transaction.category,
                        "keyword_match": {
                            "category": match.category_name,
                            "confidence": match.confidence,
                            "matched_keywords": match.matched_keywords
                        },
                        "categories_match": transaction.category == match.category_name
                    })
        
        return analysis
    
    def suggest_keywords_from_statement(
        self, 
        statement_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Analyze uncategorized transactions and suggest keywords that could be added.
        """
        statement = self.db.query(Statement).filter(Statement.id == statement_id).first()
        if not statement:
            raise ValidationError("Statement not found")
        
        # Get uncategorized transactions
        uncategorized = self.db.query(Transaction).filter(
            Transaction.statement_id == statement_id,
            Transaction.category == 'Uncategorized'
        ).all()
        
        # Analyze merchant names and descriptions for common patterns
        merchants = {}
        descriptions = {}
        
        for txn in uncategorized:
            merchant = txn.merchant.lower().strip()
            description = (txn.description or "").lower().strip()
            
            if merchant:
                merchants[merchant] = merchants.get(merchant, 0) + 1
            
            if description and description != merchant:
                descriptions[description] = descriptions.get(description, 0) + 1
        
        # Sort by frequency
        common_merchants = sorted(merchants.items(), key=lambda x: x[1], reverse=True)[:10]
        common_descriptions = sorted(descriptions.items(), key=lambda x: x[1], reverse=True)[:10]
        
        suggestions = {
            "statement_id": str(statement_id),
            "uncategorized_count": len(uncategorized),
            "suggested_keywords": {
                "common_merchants": [
                    {"keyword": merchant, "frequency": count, "suggested_as": "merchant_name"}
                    for merchant, count in common_merchants
                ],
                "common_descriptions": [
                    {"keyword": desc, "frequency": count, "suggested_as": "description_pattern"}
                    for desc, count in common_descriptions
                ]
            },
            "recommendation": "Add these common merchants/descriptions as keywords to categorize future transactions automatically."
        }
        
        return suggestions
