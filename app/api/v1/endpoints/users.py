from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional
import uuid
import shutil
import os
from pathlib import Path

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.core.security import verify_password, get_password_hash
from app.models.user import User
from app.schemas.user import (
    UserProfile, 
    UserWithProfile, 
    UserProfileUpdate, 
    UserNotificationPreferences, 
    UserPasswordUpdate,
    AccountDeletionRequest
)
from app.core.config import settings

router = APIRouter()

@router.get("/profile", response_model=UserWithProfile)
async def get_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user's complete profile"""
    return current_user

@router.put("/profile", response_model=UserProfile)
async def update_user_profile(
    profile_update: UserProfileUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update user profile information"""
    update_data = profile_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/profile/photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Upload user profile photo"""
    # Validate file type
    if not file.content_type.startswith('image/'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image"
        )
    
    # Check file size (1MB max)
    file_size = 0
    content = await file.read()
    file_size = len(content)
    
    if file_size > 1024 * 1024:  # 1MB
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be less than 1MB"
        )
    
    # Create uploads directory if it doesn't exist
    upload_dir = Path(settings.UPLOAD_DIR) / "profile_photos"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    file_extension = file.filename.split('.')[-1]
    filename = f"{current_user.id}.{file_extension}"
    file_path = upload_dir / filename
    
    # Save file
    with open(file_path, "wb") as buffer:
        buffer.write(content)
    
    # Update user profile picture URL
    current_user.profile_picture_url = f"/uploads/profile_photos/{filename}"
    db.commit()
    
    return {"message": "Profile photo updated successfully", "url": current_user.profile_picture_url}

@router.get("/notifications", response_model=UserNotificationPreferences)
async def get_notification_preferences(
    current_user: User = Depends(get_current_active_user)
):
    """Get user notification preferences"""
    return UserNotificationPreferences(
        budget_alerts_enabled=current_user.budget_alerts_enabled,
        payment_reminders_enabled=current_user.payment_reminders_enabled,
        transaction_alerts_enabled=current_user.transaction_alerts_enabled,
        weekly_summary_enabled=current_user.weekly_summary_enabled,
        monthly_reports_enabled=current_user.monthly_reports_enabled,
        email_notifications_enabled=current_user.email_notifications_enabled,
        push_notifications_enabled=current_user.push_notifications_enabled
    )

@router.put("/notifications", response_model=UserNotificationPreferences)
async def update_notification_preferences(
    preferences: UserNotificationPreferences,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update user notification preferences"""
    current_user.budget_alerts_enabled = preferences.budget_alerts_enabled
    current_user.payment_reminders_enabled = preferences.payment_reminders_enabled
    current_user.transaction_alerts_enabled = preferences.transaction_alerts_enabled
    current_user.weekly_summary_enabled = preferences.weekly_summary_enabled
    current_user.monthly_reports_enabled = preferences.monthly_reports_enabled
    current_user.email_notifications_enabled = preferences.email_notifications_enabled
    current_user.push_notifications_enabled = preferences.push_notifications_enabled
    
    db.commit()
    db.refresh(current_user)
    
    return preferences

@router.put("/password")
async def update_password(
    password_update: UserPasswordUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update user password"""
    # Verify current password
    if not verify_password(password_update.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    current_user.password_hash = get_password_hash(password_update.new_password)
    db.commit()
    
    return {"message": "Password updated successfully"}

@router.delete("/account")
async def delete_account(
    deletion_request: AccountDeletionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete user account permanently (Danger Zone)"""
    # Verify password
    if not verify_password(deletion_request.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is incorrect"
        )
    
    # Delete user (cascade will handle related records)
    db.delete(current_user)
    db.commit()
    
    return {"message": "Account deleted permanently"}

@router.get("/account/stats")
async def get_account_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get account statistics for user"""
    from app.models.card import Card
    from app.models.transaction import Transaction
    from app.models.budget import Budget
    from app.models.statement import Statement
    from app.models.alert import Alert
    
    stats = {
        "total_cards": db.query(Card).filter(Card.user_id == current_user.id).count(),
        "total_transactions": db.query(Transaction).join(Card).filter(Card.user_id == current_user.id).count(),
        "total_budgets": db.query(Budget).filter(Budget.user_id == current_user.id).count(),
        "total_statements": db.query(Statement).filter(Statement.user_id == current_user.id).count(),
        "total_alerts": db.query(Alert).filter(Alert.user_id == current_user.id).count(),
        "account_created": current_user.created_at.strftime("%B %d, %Y"),
        "last_updated": current_user.updated_at.strftime("%B %d, %Y") if current_user.updated_at else None
    }
    
    return stats
