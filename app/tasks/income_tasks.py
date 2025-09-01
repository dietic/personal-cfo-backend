from celery import shared_task
from sqlalchemy.orm import sessionmaker
import logging

from app.core.database import engine
from app.services.income_service import IncomeService

logger = logging.getLogger(__name__)

@shared_task
def process_recurring_incomes_task():
    """Celery task to process recurring incomes"""
    logger.info("Starting recurring income processing task")
    
    # Create a new database session for the task
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_local()
    
    try:
        income_service = IncomeService(db)
        created_count = income_service.process_recurring_incomes()
        
        logger.info(f"Recurring income processing completed. Created {created_count} new income records.")
        return {"status": "success", "created_count": created_count}
        
    except Exception as e:
        logger.error(f"Error processing recurring incomes: {str(e)}")
        return {"status": "error", "error": str(e)}
        
    finally:
        db.close()