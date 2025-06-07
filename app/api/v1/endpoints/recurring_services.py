from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.models.recurring_service import RecurringService
from app.schemas.recurring_service import RecurringServiceCreate, RecurringServiceUpdate, RecurringService as RecurringServiceSchema

router = APIRouter()

@router.get("/", response_model=List[RecurringServiceSchema])
async def get_recurring_services(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all recurring services for the current user"""
    services = db.query(RecurringService).filter(RecurringService.user_id == current_user.id).all()
    return services

@router.post("/", response_model=RecurringServiceSchema)
async def create_recurring_service(
    service_create: RecurringServiceCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new recurring service"""
    service = RecurringService(**service_create.dict(), user_id=current_user.id)
    db.add(service)
    db.commit()
    db.refresh(service)
    return service

@router.get("/{service_id}", response_model=RecurringServiceSchema)
async def get_recurring_service(
    service_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific recurring service"""
    service = db.query(RecurringService).filter(
        RecurringService.id == service_id,
        RecurringService.user_id == current_user.id
    ).first()
    
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring service not found"
        )
    
    return service

@router.put("/{service_id}", response_model=RecurringServiceSchema)
async def update_recurring_service(
    service_id: uuid.UUID,
    service_update: RecurringServiceUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a recurring service"""
    service = db.query(RecurringService).filter(
        RecurringService.id == service_id,
        RecurringService.user_id == current_user.id
    ).first()
    
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring service not found"
        )
    
    update_data = service_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(service, field, value)
    
    db.commit()
    db.refresh(service)
    return service

@router.delete("/{service_id}")
async def delete_recurring_service(
    service_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a recurring service"""
    service = db.query(RecurringService).filter(
        RecurringService.id == service_id,
        RecurringService.user_id == current_user.id
    ).first()
    
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring service not found"
        )
    
    db.delete(service)
    db.commit()
    return {"message": "Recurring service deleted successfully"}
