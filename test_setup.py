"""
Test script to verify the PersonalCFO backend setup
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from app.core.config import settings
from app.core.database import get_db, SessionLocal
from app.models.user import User
from app.services.user_service import UserService
from app.schemas.user import UserCreate
import asyncio


async def test_setup():
    print("🚀 Testing PersonalCFO Backend Setup")
    print("=" * 50)
    
    # Test 1: Configuration
    print(f"✅ Database URL: {settings.DATABASE_URL}")
    print(f"✅ Debug mode: {settings.DEBUG}")
    
    # Test 2: Database connection
    try:
        db = SessionLocal()
        result = db.execute("SELECT 1").fetchone()
        db.close()
        print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return
    
    # Test 3: Create a test user
    try:
        user_service = UserService()
        test_user = UserCreate(
            email="test@example.com",
            password="testpassword123"
        )
        
        db = SessionLocal()
        created_user = await user_service.create_user(db, test_user)
        print(f"✅ User creation successful: {created_user.email}")
        
        # Test authentication
        authenticated_user = await user_service.authenticate_user(db, "test@example.com", "testpassword123")
        if authenticated_user:
            print("✅ User authentication successful")
        else:
            print("❌ User authentication failed")
        
        db.close()
    except Exception as e:
        print(f"❌ User operations failed: {e}")
    
    print("=" * 50)
    print("🎉 Setup test completed!")


if __name__ == "__main__":
    # Set environment variable for testing
    os.environ["DATABASE_URL"] = "sqlite:///./personalcfo.db"
    asyncio.run(test_setup())
