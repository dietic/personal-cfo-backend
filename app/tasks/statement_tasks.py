"""
Background tasks for statement processing
"""
import logging
import uuid
from typing import Optional
from celery import current_task
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.universal_statement_service import UniversalStatementService
from app.models.statement import Statement

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="process_statement_background")
def process_statement_background(
    self,
    statement_id: str,
    file_content_base64: str,
    password: Optional[str] = None
):
    """
    Background task to process uploaded statements with AI extraction

    Args:
        statement_id: ID of the statement record in database
        file_content_base64: Base64 encoded file content
        password: Optional password for encrypted PDFs
    """
    import base64

    db = SessionLocal()
    try:
        # Update task status
        current_task.update_state(
            state='PROCESSING',
            meta={'status': 'Starting AI extraction...', 'progress': 10}
        )

        # Get statement record
        statement = db.query(Statement).filter(Statement.id == statement_id).first()
        if not statement:
            logger.error(f"Statement {statement_id} not found in database")
            # Try to check if there are any statements at all
            all_statements = db.query(Statement).count()
            logger.error(f"Total statements in database: {all_statements}")
            raise Exception(f"Statement {statement_id} not found")

        # Update statement status
        statement.status = "processing"
        statement.processing_message = "Extracting transactions with AI..."
        db.commit()

        # Decode file content
        file_content = base64.b64decode(file_content_base64)

        # Update progress
        current_task.update_state(
            state='PROCESSING',
            meta={'status': 'Processing with AI...', 'progress': 30}
        )

        # Process with Universal Statement Service
        service = UniversalStatementService(db)

        # Process the statement
        result = service.process_statement(
            statement_id=uuid.UUID(statement_id),
            file_content=file_content,
            password=password
        )

        # Update progress
        current_task.update_state(
            state='PROCESSING',
            meta={'status': 'Saving transactions...', 'progress': 80}
        )

        # Update statement with results
        statement.status = "completed"
        statement.transactions_count = result.get("transactions_count", 0)
        statement.extraction_method = result.get("extraction_method", "ai")
        statement.processing_message = f"Successfully processed {result.get('transactions_count', 0)} transactions"
        db.commit()

        # Final update
        current_task.update_state(
            state='SUCCESS',
            meta={
                'status': 'Completed successfully!',
                'progress': 100,
                'transactions_count': result.get("transactions_count", 0),
                'extraction_method': result.get("extraction_method", "ai")
            }
        )

        logger.info(f"✅ Background processing completed for statement {statement_id}")
        return {
            'status': 'completed',
            'transactions_count': result.get("transactions_count", 0),
            'extraction_method': result.get("extraction_method", "ai")
        }

    except Exception as e:
        # Get fresh statement reference for error handling
        try:
            db.rollback()  # Rollback any pending transaction
            statement = db.query(Statement).filter(Statement.id == statement_id).first()
            if statement:
                statement.status = "failed"
                statement.processing_message = f"Processing failed: {str(e)}"
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update statement status: {str(db_error)}")

        # Update task with error
        current_task.update_state(
            state='FAILURE',
            meta={'status': f'Error: {str(e)}', 'progress': 0}
        )

        logger.error(f"❌ Background processing failed for statement {statement_id}: {str(e)}")
        raise

    finally:
        db.close()

@celery_app.task(name="process_statement_premium")
def process_statement_premium(statement_id: str, file_content_base64: str, password: Optional[str] = None):
    """
    Premium processing task with higher priority
    Future: for premium subscription users
    """
    return process_statement_background(statement_id, file_content_base64, password)
