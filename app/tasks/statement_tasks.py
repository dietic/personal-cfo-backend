import uuid
import logging
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from celery import current_task

from app.core.celery_app import celery_app
from app.core.config import settings
from app.services.universal_statement_service import UniversalStatementService

logger = logging.getLogger(__name__)

# Create database session for tasks
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_statement_task(self, statement_id: str, user_id: str, bank_name: Optional[str] = None, password: Optional[str] = None):
    """Celery task to process statement - extraction and categorization"""
    db = SessionLocal()
    
    try:
        logger.info(f"🔄 Starting Celery task for statement {statement_id} (user: {user_id})")
        
        # Update task state to indicate processing has started
        current_task.update_state(
            state="PROCESSING",
            meta={"message": "Processing statement...", "progress": 10}
        )
        
        service = UniversalStatementService(db)
        
        logger.info(f"🤖 Starting extraction and categorization for {bank_name} statement")
        
        # Update progress
        current_task.update_state(
            state="PROCESSING",
            meta={"message": "Extracting transactions...", "progress": 30}
        )
        
        # Process the statement
        result = service.process_statement(
            statement_id=uuid.UUID(statement_id),
            password=password,
            bank_name=bank_name
        )
        
        # Update progress
        current_task.update_state(
            state="PROCESSING",
            meta={"message": "Categorizing transactions...", "progress": 80}
        )
        
        logger.info(f"✅ Successfully processed statement {statement_id}")
        logger.info(f"📊 Extraction and categorization completed: {result.get('transactions_count', 0)} transactions")
        
        # Final success state
        return {
            "status": "completed",
            "message": "Statement processed successfully",
            "statement_id": statement_id,
            "transactions_count": result.get("transactions_count", 0),
            "extraction_status": result.get("status", "unknown")
        }
        
    except Exception as e:
        logger.error(f"❌ Error processing statement {statement_id}: {str(e)}")
        
        # Update statement status to failed in database
        try:
            from app.models.statement import Statement
            stmt = db.query(Statement).filter(Statement.id == uuid.UUID(statement_id)).first()
            if stmt:
                stmt.processing_status = "failed"
                stmt.error_message = str(e)
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update statement status: {db_error}")
        
        # Retry the task if possible
        if self.request.retries < self.max_retries:
            logger.info(f"🔄 Retrying task for statement {statement_id} (attempt {self.request.retries + 1})")
            raise self.retry(exc=e)
        
        # Final failure
        return {
            "status": "failed",
            "message": f"Statement processing failed: {str(e)}",
            "statement_id": statement_id,
            "error": str(e)
        }
    
    finally:
        db.close()
        logger.info(f"🏁 Task completed for statement {statement_id}")

@celery_app.task
def cleanup_old_statements():
    """Periodic task to cleanup old temporary files"""
    logger.info("🧹 Starting cleanup of old statement files")
    # Implementation for cleanup logic
    return {"status": "completed", "message": "Cleanup completed"}
