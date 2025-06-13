from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional, Tuple
import json
import uuid
import logging
from datetime import datetime

from app.models.statement import Statement
from app.models.transaction import Transaction
from app.models.card import Card
from app.services.statement_parser import StatementParser
from app.services.categorization_service import CategorizationService, CategorizationResult
from app.services.category_service import CategoryService
from app.services.statement_context_manager import safe_statement_operation
from app.core.exceptions import ValidationError, NotFoundError

logger = logging.getLogger(__name__)


class EnhancedStatementService:
    
    @staticmethod
    def validate_statement_upload(db: Session, user_id: uuid.UUID) -> bool:
        """Validate that user has minimum required categories before upload"""
        if not CategoryService.validate_minimum_categories(db, user_id):
            raise ValidationError(
                "You must have at least 5 categories before uploading statements. "
                "Please create more categories in your profile settings."
            )
        return True
    
    @staticmethod
    def update_statement_status(
        db: Session, 
        statement_id: uuid.UUID, 
        status: Optional[str] = None,
        extraction_status: Optional[str] = None,
        categorization_status: Optional[str] = None,
        error_message: Optional[str] = None,
        increment_retry: Optional[str] = None  # "extraction" or "categorization"
    ) -> Statement:
        """Update statement processing status"""
        statement = db.query(Statement).filter(Statement.id == statement_id).first()
        if not statement:
            raise NotFoundError("Statement not found")
        
        if status:
            statement.status = status
        if extraction_status:
            statement.extraction_status = extraction_status
        if categorization_status:
            statement.categorization_status = categorization_status
        if error_message:
            statement.error_message = error_message
        
        # Handle retry count using new integer columns
        if increment_retry:
            if increment_retry == "extraction":
                statement.extraction_retries += 1
            elif increment_retry == "categorization":
                statement.categorization_retries += 1
        
        statement.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(statement)
        return statement
    
    @staticmethod
    def extract_transactions(
        db: Session, 
        statement_id: uuid.UUID, 
        card_id: Optional[uuid.UUID] = None,
        card_name: Optional[str] = None,
        statement_month: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extract transactions from statement (Step 1)"""
        
        statement = db.query(Statement).filter(Statement.id == statement_id).first()
        if not statement:
            raise NotFoundError("Statement not found")
        
        # Ensure we have the actual values (fix SQLAlchemy Column access issues)
        db.refresh(statement)
        
        # Update status to extracting
        EnhancedStatementService.update_statement_status(
            db, statement_id, 
            status="extracting",
            extraction_status="in_progress"
        )
        
        try:
            # Get allowed categories for AI processing
            from app.services.category_service import CategoryService
            allowed_categories = CategoryService.get_category_names_for_ai(db, statement.user_id)
            
            # Parse the statement file
            parser = StatementParser()
            
            if statement.file_type.lower() == 'pdf':
                transactions_data = parser.parse_pdf(statement.file_path, allowed_categories)
            elif statement.file_type.lower() == 'csv':
                transactions_data = parser.parse_csv(statement.file_path)
            else:
                raise ValueError(f"Unsupported file type: {statement.file_type}")
            
            if not transactions_data:
                raise ValueError("No transactions found in statement")
            
            # Get or create card
            card = None
            if card_id:
                card = db.query(Card).filter(
                    Card.id == card_id,
                    Card.user_id == statement.user_id
                ).first()
            elif card_name:
                card = db.query(Card).filter(
                    Card.user_id == statement.user_id,
                    Card.card_name.ilike(f"%{card_name}%")
                ).first()
            
            if not card:
                # Create a new card if none found
                card = Card(
                    user_id=statement.user_id,
                    card_name=card_name or f"Card from {statement.filename}",
                    card_type="credit"  # Default type
                )
                db.add(card)
                db.commit()
                db.refresh(card)
            
            # Create transaction objects (without categories)
            transactions = []
            for trans_data in transactions_data:
                # Ensure we have a valid date
                transaction_date = trans_data.get('transaction_date') or trans_data.get('date')
                if not transaction_date:
                    from datetime import datetime
                    transaction_date = datetime.now().date()
                
                # Ensure we have a valid merchant name
                merchant = trans_data.get('merchant', 'Unknown Merchant')
                if not merchant or not merchant.strip():
                    merchant = 'Unknown Merchant'
                
                transaction = Transaction(
                    card_id=card.id,
                    merchant=merchant.strip(),
                    amount=trans_data.get('amount', 0.0),
                    currency=trans_data.get('currency', 'USD'),
                    transaction_date=transaction_date,
                    description=trans_data.get('description', ''),
                    category=None,  # Will be set during categorization
                    ai_confidence=None
                )
                transactions.append(transaction)
            
            # Save transactions to database
            db.add_all(transactions)
            
            # Update statement with extracted data
            statement.processed_transactions = json.dumps([
                {
                    "id": str(trans.id),
                    "merchant": trans.merchant,
                    "amount": float(trans.amount),
                    "currency": trans.currency,
                    "date": trans.transaction_date.isoformat() if trans.transaction_date else None,
                    "description": trans.description
                }
                for trans in transactions
            ])
            
            # Update status to extracted
            EnhancedStatementService.update_statement_status(
                db, statement_id,
                status="extracted",
                extraction_status="completed",
                categorization_status="pending"
            )
            
            logger.info(f"Successfully extracted {len(transactions)} transactions from statement {statement_id}")
            
            return {
                "statement_id": statement_id,
                "transactions_found": len(transactions),
                "card_id": card.id,
                "card_name": card.card_name,
                "status": "extracted",
                "message": f"Successfully extracted {len(transactions)} transactions"
            }
            
        except Exception as e:
            logger.error(f"Extraction failed for statement {statement_id}: {str(e)}")
            
            EnhancedStatementService.update_statement_status(
                db, statement_id,
                status="failed",
                extraction_status="failed",
                error_message=f"Extraction failed: {str(e)}",
                increment_retry="extraction"
            )
            
            raise ValidationError(f"Failed to extract transactions: {str(e)}")
    
    @staticmethod
    def categorize_transactions(
        db: Session,
        statement_id: uuid.UUID,
        use_ai: bool = True,
        use_keywords: bool = True
    ) -> Dict[str, Any]:
        """Categorize extracted transactions (Step 2)"""
        
        statement = db.query(Statement).filter(Statement.id == statement_id).first()
        if not statement:
            raise NotFoundError("Statement not found")
        
        if statement.extraction_status != "completed":
            raise ValidationError("Statement transactions must be extracted before categorization")
        
        # Update status to categorizing
        EnhancedStatementService.update_statement_status(
            db, statement_id,
            status="categorizing",
            categorization_status="in_progress"
        )
        
        try:
            # Get transactions from this statement
            if not statement.processed_transactions:
                raise ValueError("No extracted transactions found")
            
            transaction_data = json.loads(statement.processed_transactions)
            
            # Check if transaction IDs are valid
            valid_transaction_ids = []
            for t in transaction_data:
                if t.get("id") and t["id"] != "None" and t["id"] != "null":
                    try:
                        valid_transaction_ids.append(uuid.UUID(t["id"]))
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid transaction ID: {t['id']}")
                        continue
                else:
                    logger.warning(f"Transaction has no valid ID: {t}")
                    
            if not valid_transaction_ids:
                # If no valid IDs found, look for transactions by statement directly
                logger.info("No valid transaction IDs found, searching by statement and date")
                
                # Try to find transactions that match this statement's criteria
                transactions = db.query(Transaction).join(Card).filter(
                    Card.user_id == statement.user_id
                ).all()
                
                # Filter transactions that might belong to this statement
                # This is a fallback approach - in production you'd want better tracking
                if not transactions:
                    raise ValueError("No transactions found for categorization")
                    
                logger.info(f"Found {len(transactions)} total user transactions for fallback categorization")
            else:
                transactions = db.query(Transaction).filter(
                    Transaction.id.in_(valid_transaction_ids)
                ).all()
            
            if not transactions:
                raise ValueError("No transactions found for categorization")
            
            # Perform categorization
            categorization_result = CategorizationService.categorize_transactions(
                db=db,
                user_id=statement.user_id,
                transactions=transactions,
                use_ai=use_ai,
                use_keywords=use_keywords
            )
            
            # Update statement status to completed
            EnhancedStatementService.update_statement_status(
                db, statement_id,
                status="completed",
                categorization_status="completed"
            )
            
            # Mark as processed
            statement.is_processed = True
            db.commit()
            
            logger.info(f"Successfully categorized {categorization_result.total_transactions} transactions for statement {statement_id}")
            
            return {
                "statement_id": statement_id,
                "transactions_categorized": categorization_result.total_transactions,
                "ai_categorized": categorization_result.ai_categorized,
                "keyword_categorized": categorization_result.keyword_categorized,
                "uncategorized": categorization_result.uncategorized,
                "status": "completed",
                "message": "Categorization completed successfully",
                "categorization_details": categorization_result.categorization_details
            }
            
        except Exception as e:
            logger.error(f"Categorization failed for statement {statement_id}: {str(e)}")
            
            EnhancedStatementService.update_statement_status(
                db, statement_id,
                status="failed",
                categorization_status="failed",
                error_message=f"Categorization failed: {str(e)}",
                increment_retry="categorization"
            )
            
            raise ValidationError(f"Failed to categorize transactions: {str(e)}")
    
    @staticmethod
    def retry_step(
        db: Session,
        statement_id: uuid.UUID,
        step: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Retry a failed extraction or categorization step"""
        
        statement = db.query(Statement).filter(Statement.id == statement_id).first()
        if not statement:
            raise NotFoundError("Statement not found")
        
        # Check retry limits
        try:
            retry_data = json.loads(statement.retry_count) if statement.retry_count else {"extraction": 0, "categorization": 0}
        except json.JSONDecodeError:
            retry_data = {"extraction": 0, "categorization": 0}
        
        max_retries = 3
        if retry_data.get(step, 0) >= max_retries:
            raise ValidationError(f"Maximum retry attempts ({max_retries}) exceeded for {step}")
        
        if step == "extraction":
            return EnhancedStatementService.extract_transactions(
                db=db,
                statement_id=statement_id,
                **kwargs
            )
        elif step == "categorization":
            return EnhancedStatementService.categorize_transactions(
                db=db,
                statement_id=statement_id,
                **kwargs
            )
        else:
            raise ValidationError(f"Invalid step: {step}")
    
    @staticmethod
    def get_statement_status(db: Session, statement_id: uuid.UUID) -> Dict[str, Any]:
        """Get detailed status information for polling"""
        
        statement = db.query(Statement).filter(Statement.id == statement_id).first()
        if not statement:
            raise NotFoundError("Statement not found")
        
        try:
            retry_data = json.loads(statement.retry_count) if statement.retry_count else {"extraction": 0, "categorization": 0}
        except json.JSONDecodeError:
            retry_data = {"extraction": 0, "categorization": 0}
        
        # Calculate progress percentage
        progress = 0
        current_step = "uploading"
        
        if statement.status == "uploaded":
            progress = 10
            current_step = "ready for extraction"
        elif statement.status == "extracting":
            progress = 30
            current_step = "extracting transactions"
        elif statement.status == "extracted":
            progress = 60
            current_step = "ready for categorization"
        elif statement.status == "categorizing":
            progress = 80
            current_step = "categorizing transactions"
        elif statement.status == "completed":
            progress = 100
            current_step = "completed"
        elif statement.status == "failed":
            progress = 0
            current_step = "failed"
        
        # Estimate completion time
        estimated_completion = None
        if statement.status in ["extracting", "categorizing"]:
            estimated_completion = "1-2 minutes"
        elif statement.status in ["uploaded", "extracted"]:
            estimated_completion = "Ready for next step"
        
        return {
            "statement_id": statement_id,
            "status": statement.status,
            "extraction_status": statement.extraction_status,
            "categorization_status": statement.categorization_status,
            "retry_count": retry_data,
            "error_message": statement.error_message,
            "progress_percentage": progress,
            "current_step": current_step,
            "estimated_completion": estimated_completion,
            "is_processed": statement.is_processed,
            "created_at": statement.created_at.isoformat(),
            "updated_at": statement.updated_at.isoformat() if statement.updated_at else None
        }
