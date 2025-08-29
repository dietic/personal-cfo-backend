#!/usr/bin/env python3
"""
Script to create test users for each user type.
Creates: free@personal-cfo.io, plus@personal-cfo.io, pro@personal-cfo.io, admin@personal-cfo.io
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.core.database import engine, get_db
from app.models.user import User, UserTypeEnum
from app.core.security import get_password_hash
import uuid

def create_test_users():
    """Create test users for each user type"""
    
    # Get database session
    db = next(get_db())
    
    test_users = [
        {
            "email": "free@personal-cfo.io",
            "plan_tier": UserTypeEnum.FREE,
            "is_admin": False,
            "first_name": "Free",
            "last_name": "User"
        },
        {
            "email": "plus@personal-cfo.io", 
            "plan_tier": UserTypeEnum.PLUS,
            "is_admin": False,
            "first_name": "Plus",
            "last_name": "User"
        },
        {
            "email": "pro@personal-cfo.io",
            "plan_tier": UserTypeEnum.PRO, 
            "is_admin": False,
            "first_name": "Pro",
            "last_name": "User"
        },
        {
            "email": "admin@personal-cfo.io",
            "plan_tier": UserTypeEnum.FREE,
            "is_admin": True,
            "first_name": "Admin",
            "last_name": "User"
        }
    ]
    
    # Default password for all test users
    default_password = "Lima2023$"
    password_hash = get_password_hash(default_password)
    
    for user_data in test_users:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == user_data["email"]).first()
        
        if existing_user:
            print(f"User {user_data['email']} already exists, updating...")
            # Update existing user
            existing_user.plan_tier = user_data["plan_tier"]
            existing_user.is_admin = user_data["is_admin"]
            existing_user.first_name = user_data["first_name"]
            existing_user.last_name = user_data["last_name"]
            existing_user.is_active = True  # Make sure they're active
            existing_user.plan_status = "active"
        else:
            print(f"Creating user {user_data['email']}...")
            # Create new user
            new_user = User(
                id=uuid.uuid4(),
                email=user_data["email"],
                password_hash=password_hash,
                plan_tier=user_data["plan_tier"],
                is_admin=user_data["is_admin"],
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
                is_active=True,  # Make them active immediately
                plan_status="active"
            )
            db.add(new_user)
    
    try:
        db.commit()
        print("Test users created/updated successfully!")
        print("\nTest Users:")
        print("- free@personal-cfo.io (password: Lima2023$) - Free tier")
        print("- plus@personal-cfo.io (password: Lima2023$) - Plus tier") 
        print("- pro@personal-cfo.io (password: Lima2023$) - Pro tier")
        print("- admin@personal-cfo.io (password: Lima2023$) - Admin tier")
        
    except Exception as e:
        db.rollback()
        print(f"Error creating users: {e}")
        
    finally:
        db.close()

if __name__ == "__main__":
    create_test_users()