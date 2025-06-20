from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

class BankProviderBase(BaseModel):
    """
    Base schema for bank provider data.
    
    Think of this as the 'business card' format for banks - it defines
    what information we standardize across all bank entries.
    """
    name: str
    short_name: Optional[str] = None
    country: str  # ISO country code like "PE", "US"
    country_name: str  # Human readable like "Peru", "United States"
    logo_url: Optional[str] = None
    website: Optional[str] = None
    color_primary: Optional[str] = None
    color_secondary: Optional[str] = None  # For gradient backgrounds, accent elements
    is_active: bool = True
    is_popular: bool = False

class BankProviderCreate(BankProviderBase):
    """Schema for creating a new bank provider - admin only operation"""
    pass

class BankProviderUpdate(BaseModel):
    """Schema for updating bank provider - admin only operation"""
    name: Optional[str] = None
    short_name: Optional[str] = None
    country: Optional[str] = None
    country_name: Optional[str] = None
    logo_url: Optional[str] = None
    website: Optional[str] = None
    color_primary: Optional[str] = None
    color_secondary: Optional[str] = None
    is_active: Optional[bool] = None
    is_popular: Optional[bool] = None

class BankProvider(BankProviderBase):
    """Complete bank provider schema with metadata"""
    id: uuid.UUID
    created_at: datetime
    
    class Config:
        from_attributes = True

class BankProviderSimple(BaseModel):
    """Lightweight schema for dropdowns and card display"""
    id: uuid.UUID
    name: str
    short_name: Optional[str] = None
    country: str
    is_popular: bool = False  # For sorting popular banks first
    color_primary: Optional[str] = None  # For card theming
    color_secondary: Optional[str] = None  # For card theming
    
    class Config:
        from_attributes = True
    
    @property
    def display_name(self) -> str:
        """Returns short_name if available, otherwise full name"""
        return self.short_name if self.short_name else self.name
