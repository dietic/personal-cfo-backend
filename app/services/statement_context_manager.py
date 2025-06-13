"""
Statement Context Manager - Safe operations with automatic rollback
This provides atomic operations for statement processing with proper error handling
"""

from contextlib import contextmanager
from sqlalchemy.orm import Session
import uuid
import logging
from datetime import datetime
from typing import Generator

from app.models.statement import Statement

logger = logging.getLogger(__name__)


@contextmanager
def safe_statement_operation(
    db: Session, 
    statement_id: uuid.UUID, 
    operation_name: str
) -> Generator[Statement, None, None]:
    """
    Context manager for safe statement operations with automatic rollback
    
    Args:
        db: Database session
        statement_id: UUID of the statement to operate on
        operation_name: Name of operation ('extract' or 'categorize')
    
    Yields:
        Statement: The locked statement object
        
    Raises:
        ValueError: If statement not found
        Exception: Any processing error (will be caught and status updated)
    """
    statement = None
    original_status = None
    
    try:
        # Lock the statement for update to prevent race conditions
        statement = db.query(Statement).filter(
            Statement.id == statement_id
        ).with_for_update().first()
        
        if not statement:
            raise ValueError(f"Statement {statement_id} not found")
        
        # Store original status for potential rollback
        original_status = {
            'status': statement.status,
            'extraction_status': statement.extraction_status,
            'categorization_status': statement.categorization_status,
            'error_message': statement.error_message
        }
        
        # Set status to processing
        statement.status = f"{operation_name}ing"
        statement.error_message = None
        statement.updated_at = datetime.utcnow()
        
        if operation_name == "extract":
            statement.extraction_status = "in_progress"
        elif operation_name == "categorize":
            statement.categorization_status = "in_progress"
        
        # Commit the status change
        db.commit()
        logger.info(f"Started {operation_name} for statement {statement_id}")
        
        # Yield the statement for processing
        yield statement
        
        # If we get here, operation succeeded
        statement.status = f"{operation_name}ed" if operation_name != "categorize" else "completed"
        statement.updated_at = datetime.utcnow()
        
        if operation_name == "extract":
            statement.extraction_status = "completed"
            statement.categorization_status = "pending"
        elif operation_name == "categorize":
            statement.categorization_status = "completed"
            statement.is_processed = True
        
        db.commit()
        logger.info(f"Successfully completed {operation_name} for statement {statement_id}")
        
    except Exception as e:
        logger.error(f"Failed {operation_name} for statement {statement_id}: {str(e)}")
        
        # Roll back any uncommitted changes
        db.rollback()
        
        if statement:
            try:
                # Update statement with error status
                statement.status = "failed"
                statement.error_message = str(e)
                statement.updated_at = datetime.utcnow()
                
                if operation_name == "extract":
                    statement.extraction_status = "failed"
                    # Increment extraction retry count if column exists
                    if hasattr(statement, 'extraction_retries'):
                        statement.extraction_retries = (statement.extraction_retries or 0) + 1
                elif operation_name == "categorize":
                    statement.categorization_status = "failed"
                    # Increment categorization retry count if column exists
                    if hasattr(statement, 'categorization_retries'):
                        statement.categorization_retries = (statement.categorization_retries or 0) + 1
                
                db.commit()
                logger.info(f"Updated statement {statement_id} status to failed")
                
            except Exception as inner_e:
                logger.error(f"Failed to update error status for statement {statement_id}: {str(inner_e)}")
                db.rollback()
        
        # Re-raise the original exception
        raise


class StatementOperationManager:
    """
    Helper class for managing statement operations with retry logic
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def can_retry(self, statement: Statement, operation: str) -> bool:
        """
        Check if a statement can be retried for the given operation
        
        Args:
            statement: Statement object
            operation: 'extract' or 'categorize'
            
        Returns:
            bool: True if retry is allowed, False otherwise
        """
        max_retries = getattr(statement, 'max_retries', 3)
        
        if operation == "extract":
            current_retries = getattr(statement, 'extraction_retries', 0)
        elif operation == "categorize":
            current_retries = getattr(statement, 'categorization_retries', 0)
        else:
            return False
        
        return current_retries < max_retries
    
    def get_retry_info(self, statement: Statement) -> dict:
        """
        Get retry information for a statement
        
        Args:
            statement: Statement object
            
        Returns:
            dict: Retry information including counts and limits
        """
        return {
            'extraction_retries': getattr(statement, 'extraction_retries', 0),
            'categorization_retries': getattr(statement, 'categorization_retries', 0),
            'max_retries': getattr(statement, 'max_retries', 3),
            'can_retry_extraction': self.can_retry(statement, 'extract'),
            'can_retry_categorization': self.can_retry(statement, 'categorize')
        }


# Example usage in enhanced_statement_service.py:
"""
from app.services.statement_context_manager import safe_statement_operation

@staticmethod
def extract_transactions(
    db: Session, 
    statement_id: uuid.UUID, 
    card_id: Optional[uuid.UUID] = None,
    card_name: Optional[str] = None,
    statement_month: Optional[str] = None
) -> Dict[str, Any]:
    '''Extract transactions from statement (Step 1)'''
    
    with safe_statement_operation(db, statement_id, "extract") as statement:
        # All the extraction logic here
        # If anything fails, the context manager will handle cleanup
        
        parser = StatementParser()
        
        if statement.file_type.lower() == 'pdf':
            transactions_data = parser.parse_pdf(statement.file_path)
        elif statement.file_type.lower() == 'csv':
            transactions_data = parser.parse_csv(statement.file_path)
        else:
            raise ValueError(f"Unsupported file type: {statement.file_type}")
        
        if not transactions_data:
            raise ValueError("No transactions found in statement")
        
        # Create transactions with statement_id link
        transactions = []
        for trans_data in transactions_data:
            transaction = Transaction(
                card_id=card.id,
                statement_id=statement_id,  # This is the critical fix
                merchant=trans_data.get('merchant', 'Unknown'),
                amount=trans_data.get('amount', 0.0),
                currency=trans_data.get('currency', 'USD'),
                transaction_date=trans_data.get('transaction_date'),
                description=trans_data.get('description', ''),
                category=None,
                ai_confidence=None
            )
            transactions.append(transaction)
        
        db.add_all(transactions)
        db.commit()
        
        return {
            "statement_id": statement_id,
            "transactions_found": len(transactions),
            "status": "extracted",
            "message": f"Successfully extracted {len(transactions)} transactions"
        }
"""
