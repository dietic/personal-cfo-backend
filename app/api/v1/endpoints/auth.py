from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import timedelta

from app.core.database import get_db
from app.core.security import create_access_token
from app.core.deps import get_current_user
from app.schemas.user import UserCreate, UserLogin, UserProfile, Token, OTPVerifyRequest, OTPResendRequest
from app.services.user_service import UserService
from app.utils.rate_limiter import allow_for_email
from app.core.config import settings

router = APIRouter()

@router.post("/register", response_model=UserProfile)
async def register(user_create: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    user_service = UserService(db)
    
    # Check if user already exists
    if user_service.get_user_by_email(user_create.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    user = user_service.create_user(user_create)
    return user

@router.post("/verify-otp")
async def verify_otp(payload: OTPVerifyRequest, db: Session = Depends(get_db)):
    # Per-email rate limit
    if not allow_for_email("verify", payload.email, settings.OTP_VERIFY_MAX_PER_MINUTE, 60):
        raise HTTPException(status_code=429, detail="Too many attempts, slow down.")
    svc = UserService(db)
    user = svc.get_user_by_email(payload.email)
    if user and user.otp_attempts is not None and user.otp_attempts >= settings.OTP_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many attempts. Please resend a new code.")
    ok = svc.verify_otp(payload.email, payload.code)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid or expired code")
    return {"message": "Account verified"}

@router.post("/resend-otp")
async def resend_otp(payload: OTPResendRequest, db: Session = Depends(get_db)):
    # Per-email rate limit
    if not allow_for_email("resend", payload.email, settings.OTP_RESEND_MAX_PER_MINUTE, 60):
        raise HTTPException(status_code=429, detail="Too many requests, slow down.")
    svc = UserService(db)
    user = svc.get_user_by_email(payload.email)
    # Neutralize enumeration: always return 200 with same message
    if not user:
        return {"message": "If your account exists and isn’t verified, a code has been sent."}
    if user.is_active:
        return {"message": "If your account exists and isn’t verified, a code has been sent."}
    ok = svc.resend_otp(payload.email)
    if not ok:
        # Still return neutral message to avoid enumeration
        return {"message": "If your account exists and isn’t verified, a code has been sent."}
    return {"message": "If your account exists and isn’t verified, a code has been sent."}

@router.post("/login", response_model=Token)
async def login(user_login: UserLogin, db: Session = Depends(get_db)):
    """Login user and return access token"""
    user_service = UserService(db)
    
    user = user_service.authenticate_user(user_login.email, user_login.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        # Give a hint if code exists but expired
        detail = "Account not verified. Check your email for the code."
        if user.otp_expires_at is not None:
            detail = "Account not verified. Your code may have expired; request a new one."
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )
    
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/refresh", response_model=Token)
async def refresh_token(current_user: UserProfile = Depends(get_current_user)):
    """Refresh access token"""
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": current_user.email}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

# Import here to avoid circular imports
from app.core.deps import get_current_user
