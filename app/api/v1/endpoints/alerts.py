from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid
import json
from datetime import datetime

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.models.alert import Alert
from app.schemas.alert import Alert as AlertSchema, AlertCreate, AlertUpdate
from app.models.alert import AlertType, AlertSeverity

router = APIRouter()


@router.get("/", response_model=List[AlertSchema])
async def get_alerts(
    active_only: bool = True,
    unread_only: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get alerts for the current user"""
    query = db.query(Alert).filter(Alert.user_id == current_user.id)
    
    if active_only:
        query = query.filter(Alert.is_active == True)
    
    if unread_only:
        query = query.filter(Alert.is_read == False)
    
    alerts = query.order_by(Alert.triggered_at.desc()).all()
    return alerts


@router.post("/", response_model=AlertSchema)
async def create_alert(
    alert: AlertCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new alert"""
    db_alert = Alert(
        user_id=current_user.id,
        statement_id=alert.statement_id,
        alert_type=alert.alert_type,
        severity=alert.severity,
        title=alert.title,
        description=alert.description,
        criteria=alert.criteria,
        threshold=alert.threshold,
        frequency=alert.frequency
    )
    
    db.add(db_alert)
    db.commit()
    db.refresh(db_alert)
    
    return db_alert


@router.put("/{alert_id}", response_model=AlertSchema)
async def update_alert(
    alert_id: uuid.UUID,
    alert_update: AlertUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update an alert (mark as read, acknowledge, etc.)"""
    alert = db.query(Alert).filter(
        Alert.id == alert_id,
        Alert.user_id == current_user.id
    ).first()
    
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    
    # Update fields if provided
    if alert_update.is_read is not None:
        alert.is_read = alert_update.is_read
    
    if alert_update.is_active is not None:
        alert.is_active = alert_update.is_active
    
    if alert_update.acknowledged_at is not None:
        alert.acknowledged_at = alert_update.acknowledged_at
    elif alert_update.is_read and not alert.acknowledged_at:
        alert.acknowledged_at = datetime.utcnow()
    
    db.commit()
    db.refresh(alert)
    
    return alert


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete an alert"""
    alert = db.query(Alert).filter(
        Alert.id == alert_id,
        Alert.user_id == current_user.id
    ).first()
    
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    
    db.delete(alert)
    db.commit()
    
    return {"message": "Alert deleted successfully"}


@router.post("/mark-all-read")
async def mark_all_alerts_read(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Mark all alerts as read for the current user"""
    alerts = db.query(Alert).filter(
        Alert.user_id == current_user.id,
        Alert.is_read == False
    ).all()
    
    for alert in alerts:
        alert.is_read = True
        if not alert.acknowledged_at:
            alert.acknowledged_at = datetime.utcnow()
    
    db.commit()
    
    return {"message": f"Marked {len(alerts)} alerts as read"}


@router.get("/summary")
async def get_alerts_summary(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a summary of alerts for the current user"""
    total_alerts = db.query(Alert).filter(Alert.user_id == current_user.id).count()
    unread_alerts = db.query(Alert).filter(
        Alert.user_id == current_user.id,
        Alert.is_read == False
    ).count()
    high_priority_alerts = db.query(Alert).filter(
        Alert.user_id == current_user.id,
        Alert.severity == AlertSeverity.HIGH,
        Alert.is_active == True
    ).count()
    
    return {
        "total_alerts": total_alerts,
        "unread_alerts": unread_alerts,
        "high_priority_alerts": high_priority_alerts
    }
