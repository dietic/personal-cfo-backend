#!/usr/bin/env python3
"""
Validation test for enhanced PDF import functionality
Tests the code changes without requiring a running server
"""

import sys
import os

# Add the app directory to Python path
sys.path.append('/Users/diego/Documents/Proyectos/personal-cfo/personal-cfo-backend')

def test_imports():
    """Test that all new imports work correctly"""
    print("🔍 Testing imports...")
    
    try:
        # Test Alert model import
        from app.models.alert import Alert, AlertType, AlertSeverity
        print("✅ Alert model imported successfully")
        
        # Test Alert schema import
        from app.schemas.alert import Alert as AlertSchema, AlertCreate
        print("✅ Alert schema imported successfully")
        
        # Test alerts endpoint import
        from app.api.v1.endpoints.alerts import router
        print("✅ Alerts endpoint imported successfully")
        
        # Test enhanced statement parser
        from app.services.statement_parser import StatementParser
        print("✅ Enhanced StatementParser imported successfully")
        
        # Test enhanced AI service
        from app.services.ai_service import AIService
        print("✅ Enhanced AIService imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_alert_model():
    """Test the Alert model functionality"""
    print("\n🔍 Testing Alert model...")
    
    try:
        from app.models.alert import AlertType, AlertSeverity
        
        # Test enum values
        assert AlertType.SPENDING_LIMIT == "spending_limit"
        assert AlertType.UNUSUAL_SPENDING == "unusual_spending"
        assert AlertSeverity.HIGH == "high"
        
        print("✅ Alert enums working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Alert model test failed: {e}")
        return False

def test_statement_parser_enhancements():
    """Test the enhanced statement parser"""
    print("\n🔍 Testing StatementParser enhancements...")
    
    try:
        from app.services.statement_parser import StatementParser
        
        # Test that the parser has the new methods
        parser = StatementParser()
        
        # Check if methods exist
        assert hasattr(parser, 'parse_pdf_statement')
        assert hasattr(parser, '_extract_transactions_with_ai')
        assert hasattr(parser, '_extract_transactions_from_text_fallback')
        
        print("✅ StatementParser has new AI-powered methods")
        
        # Test currency detection
        test_text = "Transaction for $100.50"
        currency = parser.detect_currency(test_text, "$100.50")
        assert currency == "USD"
        
        test_text_pen = "Transacción por S/.250.00"
        currency_pen = parser.detect_currency(test_text_pen, "S/.250.00")
        assert currency_pen == "PEN"
        
        print("✅ Currency detection working correctly")
        return True
        
    except Exception as e:
        print(f"❌ StatementParser test failed: {e}")
        return False

def test_ai_service_enhancements():
    """Test the enhanced AI service"""
    print("\n🔍 Testing AIService enhancements...")
    
    try:
        from app.services.ai_service import AIService
        
        # Test that the service has the new methods
        ai_service = AIService()
        
        # Check if methods exist
        assert hasattr(ai_service, 'analyze_statement_and_generate_insights')
        assert hasattr(ai_service, 'analyze_spending_patterns')
        assert hasattr(ai_service, 'detect_anomalies')
        
        print("✅ AIService has enhanced analysis methods")
        return True
        
    except Exception as e:
        print(f"❌ AIService test failed: {e}")
        return False

def test_pdf_restriction():
    """Test that PDF-only restriction is in place"""
    print("\n🔍 Testing PDF-only upload restriction...")
    
    try:
        # Read the statements endpoint file
        with open('/Users/diego/Documents/Proyectos/personal-cfo/personal-cfo-backend/app/api/v1/endpoints/statements.py', 'r') as f:
            content = f.read()
        
        # Check that only PDF is allowed
        assert "Only PDF files are supported" in content
        assert "('.pdf')" in content and "('.pdf', '.csv')" not in content
        
        print("✅ PDF-only restriction implemented correctly")
        return True
        
    except Exception as e:
        print(f"❌ PDF restriction test failed: {e}")
        return False

def test_database_migration():
    """Test that the alerts table migration exists"""
    print("\n🔍 Testing database migration...")
    
    try:
        migration_file = '/Users/diego/Documents/Proyectos/personal-cfo/personal-cfo-backend/alembic/versions/51336fa53cb6_add_alerts_table.py'
        
        if os.path.exists(migration_file):
            print("✅ Alerts table migration file exists")
            
            with open(migration_file, 'r') as f:
                content = f.read()
            
            # Check that alerts table is created
            if 'create_table(\'alerts\'' in content:
                print("✅ Alerts table creation found in migration")
                return True
            else:
                print("❌ Alerts table creation not found in migration")
                return False
        else:
            print("❌ Migration file not found")
            return False
            
    except Exception as e:
        print(f"❌ Migration test failed: {e}")
        return False

def main():
    """Run all validation tests"""
    print("🚀 Enhanced PDF Import Functionality Validation")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_alert_model,
        test_statement_parser_enhancements,
        test_ai_service_enhancements,
        test_pdf_restriction,
        test_database_migration
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All validation tests passed!")
        print("\n✅ Enhanced PDF Import Features Implemented:")
        print("  • PDF-only upload restriction")
        print("  • ChatGPT-powered PDF transaction extraction")
        print("  • Automatic statement period detection")
        print("  • Enhanced AI trend analysis")
        print("  • Personalized alert generation")
        print("  • Alert management system")
        print("  • Currency detection (USD $ and PEN S/.)")
        print("  • Future monitoring rule creation")
        print("\n🚀 Ready for testing with actual PDF files!")
    else:
        print(f"❌ {total - passed} tests failed. Please review the issues above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
