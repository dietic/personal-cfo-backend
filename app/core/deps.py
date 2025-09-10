from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Callable
from app.core.database import get_db
from app.core.security import verify_token
from app.models.user import User, UserTypeEnum
from app.core.permissions import Permission, has_permission

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    token = credentials.credentials
    email = verify_token(token)

    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

async def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db)
) -> User | None:
    """Return current user if Authorization header present and valid; else None."""
    auth = request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ",1)[1]
    email = verify_token(token)
    if not email:
        return None
    return db.query(User).filter(User.email == email).first()

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account has been deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user

def get_current_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Ensure current user is an admin"""
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

def require_permission(permission: Permission) -> Callable:
    """Dependency factory to require specific permission"""
    def permission_checker(current_user: User = Depends(get_current_active_user)) -> User:
        user_type = current_user.plan_tier
        is_admin = getattr(current_user, "is_admin", False)
        
        if not has_permission(user_type, permission, is_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission.value}"
            )
        return current_user
    
    return permission_checker

def require_user_type(min_user_type: UserTypeEnum) -> Callable:
    """Dependency factory to require minimum user type"""
    type_hierarchy = {
        UserTypeEnum.FREE: 0,
        UserTypeEnum.PLUS: 1,
        UserTypeEnum.PRO: 2,
    }
    
    def _user_type_checker(current_user: User) -> User:
        # Admins bypass all plan tier requirements
        if getattr(current_user, "is_admin", False):
            return current_user
            
        current_level = type_hierarchy.get(current_user.plan_tier, 0)
        required_level = type_hierarchy.get(min_user_type, 0)
        
        if current_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User type required: {min_user_type.value} or higher"
            )
        return current_user
    
    def user_type_checker(current_user: User = Depends(get_current_active_user)) -> User:
        return _user_type_checker(current_user)
    
    return user_type_checker
