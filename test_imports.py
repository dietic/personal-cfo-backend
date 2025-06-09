#!/usr/bin/env python3
"""
Import Test - Check if all modules import correctly
"""

import sys
from pathlib import Path

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent))

def test_imports():
    """Test all our custom imports"""
    try:
        print("Testing core imports...")
        from app.core.exceptions import NotFoundError, ValidationError
        print("✅ Core exceptions imported successfully")
        
        print("Testing model imports...")
        from app.models.category import Category
        from app.models.statement import Statement
        from app.models.user import User
        print("✅ Models imported successfully")
        
        print("Testing schema imports...")
        from app.schemas.category import CategoryCreate, CategoryResponse, CategoryKeywordMatch
        from app.schemas.statement import StatementStatusResponse
        print("✅ Schemas imported successfully")
        
        print("Testing service imports...")
        from app.services.category_service import CategoryService
        from app.services.categorization_service import CategorizationService, CategorizationResult
        from app.services.enhanced_statement_service import EnhancedStatementService
        print("✅ Services imported successfully")
        
        print("Testing API imports...")
        from app.api.v1.endpoints.categories import router as categories_router
        from app.api.v1.endpoints.statements import router as statements_router
        from app.api.v1.api import api_router
        print("✅ API endpoints imported successfully")
        
        print("\n🎉 All imports successful! The system should work.")
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_imports()
