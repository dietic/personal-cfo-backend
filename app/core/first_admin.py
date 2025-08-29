"""
First admin user creation on application startup.
This ensures there's always at least one admin user available.
"""
import logging
from app.core.database import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)

def create_first_admin(admin_email: str, admin_password: str):
    """
    Create the first admin user if no admins exist in the database.
    """
    db = SessionLocal()
    try:
        # Check if any admin user already exists
        existing_admin = db.query(User).filter(User.is_admin == True).first()
        if existing_admin:
            logger.info("Admin user already exists, skipping first admin creation")
            return
        
        if not admin_email or not admin_password:
            logger.warning(
                "FIRST_ADMIN_EMAIL and FIRST_ADMIN_PASSWORD not provided. "
                "Skipping first admin creation."
            )
            return
        
        # Check if email already exists (non-admin user)
        existing_user = db.query(User).filter(User.email == admin_email).first()
        if existing_user:
            # Upgrade existing user to admin
            existing_user.is_admin = True
            existing_user.is_active = True
            db.commit()
            logger.info(f"Upgraded existing user {admin_email} to admin privileges")
            return
        
        # Create new admin user
        admin_user = User(
            email=admin_email,
            password_hash=get_password_hash(admin_password),
            first_name="System",
            last_name="Administrator", 
            is_active=True,
            is_admin=True,
            plan_tier="free",
            preferred_currency="USD",
            timezone="UTC-5 (Eastern Time)"
        )
        
        db.add(admin_user)
        db.commit()
        logger.info(f"Created first admin user: {admin_email}")
        
    except Exception as e:
        logger.error(f"Error creating first admin user: {e}")
        db.rollback()
    finally:
        db.close()