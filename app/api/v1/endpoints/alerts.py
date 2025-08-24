from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.models.alert import Alert, AlertType, AlertSeverity
from app.schemas.alert import AlertCreate, Alert as AlertSchema, AlertUpdate
from app.services.plan_limits import assert_within_limit

router = APIRouter()

@router.get("/", response_model=List[AlertSchema])
async def list_alerts(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    return db.query(Alert).filter(Alert.user_id == current_user.id).all()

@router.post("/", response_model=AlertSchema)
async def create_alert(payload: AlertCreate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    assert_within_limit(db, current_user, "alerts")
    alert = Alert(
        user_id=current_user.id,
        alert_type=payload.alert_type,
        severity=payload.severity or AlertSeverity.MEDIUM,
        title=payload.title,
        message=payload.message,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert

@router.put("/{alert_id}", response_model=AlertSchema)
async def update_alert(alert_id: uuid.UUID, payload: AlertUpdate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.user_id == current_user.id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    data = payload.dict(exclude_unset=True)
    for k,v in data.items():
        setattr(alert, k, v)
    db.commit()
    db.refresh(alert)
    return alert

@router.delete("/{alert_id}")
async def delete_alert(alert_id: uuid.UUID, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.user_id == current_user.id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.delete(alert)
    db.commit()
    return {"message": "Alert deleted"}
