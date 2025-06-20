from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.bank_provider import BankProvider
from app.models.user import User
from app.schemas.bank_provider import BankProvider as BankProviderSchema, BankProviderSimple

router = APIRouter()

@router.get("/", response_model=List[BankProviderSimple])
def get_bank_providers(
    country: str = None,  # Filter by country code like "PE"
    popular_only: bool = False,  # Show only popular banks first
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get list of available bank providers.
    
    This is like browsing a directory of banks - users need this to select
    their bank when creating cards. We can filter by country to show only
    relevant banks (e.g., only Peruvian banks for Peruvian users).
    
    Query Parameters:
    - country: ISO country code (PE, US, MX, etc.)
    - popular_only: If true, prioritize popular banks
    """
    query = db.query(BankProvider).filter(BankProvider.is_active == True)
    
    if country:
        query = query.filter(BankProvider.country == country.upper())
    
    if popular_only:
        # Popular banks first, then alphabetical
        query = query.order_by(BankProvider.is_popular.desc(), BankProvider.name)
    else:
        # Just alphabetical
        query = query.order_by(BankProvider.name)
    
    return query.all()

@router.get("/{bank_id}", response_model=BankProviderSchema)
def get_bank_provider(
    bank_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get detailed information about a specific bank provider"""
    bank = db.query(BankProvider).filter(BankProvider.id == bank_id).first()
    
    if not bank:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bank provider not found"
        )
    
    return bank

@router.get("/countries", response_model=List[dict])
def get_available_countries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get list of countries that have bank providers in our database.
    
    Useful for country selection dropdowns - only show countries
    where we actually have bank data.
    """
    countries = db.query(
        BankProvider.country,
        BankProvider.country_name
    ).filter(
        BankProvider.is_active == True
    ).distinct().all()
    
    return [
        {"code": country[0], "name": country[1]} 
        for country in countries
    ]
