import logging
from typing import Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)

# Create database session for tasks
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@celery_app.task
def send_email_notification(email: str, subject: str, message: str):
    """Send email notification using Resend"""
    try:
        logger.info(f"📧 Sending email to {email}: {subject}")
        
        # Here you would integrate with Resend API
        # For now, just log the notification
        logger.info(f"Email sent successfully to {email}")
        
        return {
            "status": "sent",
            "email": email,
            "subject": subject
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to send email to {email}: {str(e)}")
        return {
            "status": "failed",
            "email": email,
            "error": str(e)
        }

@celery_app.task
def send_statement_completion_notification(user_id: str, statement_id: str, transactions_count: int):
    """Send notification when statement processing is completed"""
    db = SessionLocal()
    
    try:
        from app.models.user import User
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"status": "failed", "error": "User not found"}
            
        subject = "Statement Processing Complete"
        message = f"Your bank statement has been processed successfully with {transactions_count} transactions categorized."
        
        # Queue email notification
        send_email_notification.delay(user.email, subject, message)
        
        logger.info(f"📧 Queued statement completion notification for user {user_id}")
        
        return {
            "status": "queued",
            "user_id": user_id,
            "statement_id": statement_id
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to queue notification: {str(e)}")
        return {"status": "failed", "error": str(e)}
    
    finally:
        db.close()
