from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime
import uuid
from app.models.user import CurrencyEnum, TimezoneEnum

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    preferred_currency: Optional[CurrencyEnum] = None
    timezone: Optional[TimezoneEnum] = None

class UserNotificationPreferences(BaseModel):
    budget_alerts_enabled: bool
    payment_reminders_enabled: bool
    transaction_alerts_enabled: bool
    weekly_summary_enabled: bool
    monthly_reports_enabled: bool
    email_notifications_enabled: bool
    push_notifications_enabled: bool

class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str
    confirm_new_password: str

    @validator('confirm_new_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('passwords do not match')
        return v

class UserProfile(UserBase):
    id: uuid.UUID
    is_active: bool
    is_admin: bool
    first_name: Optional[str]
    last_name: Optional[str]
    phone_number: Optional[str]
    profile_picture_url: Optional[str]
    preferred_currency: CurrencyEnum
    timezone: TimezoneEnum
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class User(UserBase):
    id: uuid.UUID
    is_active: bool
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True

class UserWithProfile(UserProfile):
    # Notification Preferences
    budget_alerts_enabled: bool
    payment_reminders_enabled: bool
    transaction_alerts_enabled: bool
    weekly_summary_enabled: bool
    monthly_reports_enabled: bool
    email_notifications_enabled: bool
    push_notifications_enabled: bool

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class AccountDeletionRequest(BaseModel):
    password: str
    confirmation_text: str

    @validator('confirmation_text')
    def confirmation_must_match(cls, v):
        if v != "DELETE MY ACCOUNT":
            raise ValueError('confirmation text must be "DELETE MY ACCOUNT"')
        return v
