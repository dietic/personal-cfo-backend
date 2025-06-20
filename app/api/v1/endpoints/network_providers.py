from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.models.network_provider import NetworkProvider
from app.schemas.network_provider import (
    NetworkProvider as NetworkProviderSchema,
    NetworkProviderCreate,
    NetworkProviderUpdate
)

router = APIRouter()

@router.get("/", response_model=List[NetworkProviderSchema])
async def get_network_providers(
    country_code: Optional[str] = None,
    active_only: bool = True,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all network providers with optional filtering.
    
    Like browsing a catalog of credit card networks - you can filter
    by country or show only active networks.
    """
    query = db.query(NetworkProvider)
    
    if active_only:
        query = query.filter(NetworkProvider.is_active == True)
    
    if country_code:
        # Show both global and country-specific providers
        query = query.filter(
            (NetworkProvider.country == country_code) |
            (NetworkProvider.country == "GLOBAL")
        )
    
    return query.order_by(NetworkProvider.name).all()

@router.post("/", response_model=NetworkProviderSchema)
async def create_network_provider(
    network_provider_create: NetworkProviderCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new network provider (admin only)"""
    # TODO: Add admin permission check
    network_provider = NetworkProvider(**network_provider_create.dict())
    db.add(network_provider)
    db.commit()
    db.refresh(network_provider)
    return network_provider

@router.get("/{network_provider_id}", response_model=NetworkProviderSchema)
async def get_network_provider(
    network_provider_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific network provider by ID"""
    network_provider = db.query(NetworkProvider).filter(
        NetworkProvider.id == network_provider_id
    ).first()
    
    if not network_provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Network provider not found"
        )
    
    return network_provider

@router.put("/{network_provider_id}", response_model=NetworkProviderSchema)
async def update_network_provider(
    network_provider_id: uuid.UUID,
    network_provider_update: NetworkProviderUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a network provider (admin only)"""
    # TODO: Add admin permission check
    network_provider = db.query(NetworkProvider).filter(
        NetworkProvider.id == network_provider_id
    ).first()
    
    if not network_provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Network provider not found"
        )
    
    for field, value in network_provider_update.dict(exclude_unset=True).items():
        setattr(network_provider, field, value)
    
    db.commit()
    db.refresh(network_provider)
    return network_provider
