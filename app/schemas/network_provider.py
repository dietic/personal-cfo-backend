from pydantic import BaseModel
from typing import Optional
import uuid

class NetworkProviderBase(BaseModel):
    name: str
    short_name: Optional[str] = None
    country: str = "GLOBAL"
    is_active: bool = True
    color_primary: Optional[str] = None
    color_secondary: Optional[str] = None
    logo_url: Optional[str] = None

class NetworkProviderCreate(NetworkProviderBase):
    pass

class NetworkProviderUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    country: Optional[str] = None
    is_active: Optional[bool] = None
    color_primary: Optional[str] = None
    color_secondary: Optional[str] = None
    logo_url: Optional[str] = None

class NetworkProvider(NetworkProviderBase):
    id: uuid.UUID
    
    class Config:
        from_attributes = True

# Simple version for use in other schemas
class NetworkProviderSimple(BaseModel):
    id: uuid.UUID
    name: str
    short_name: Optional[str] = None
    country: str
    color_primary: Optional[str] = None
    color_secondary: Optional[str] = None
    
    class Config:
        from_attributes = True
