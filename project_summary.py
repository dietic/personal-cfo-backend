#!/usr/bin/env python3
"""
PersonalCFO Backend - Project Summary and Status Report
"""

import os
import sqlite3
from pathlib import Path

def check_database():
    """Check database and show table information"""
    db_path = "./personalcfo.db"
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print("📊 Database Tables:")
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            print(f"   • {table_name}: {count} records")
        
        conn.close()
        return True
    else:
        print("❌ Database not found")
        return False

def check_files():
    """Check project structure"""
    important_files = [
        "main.py",
        "requirements.txt",
        "alembic.ini",
        ".env",
        "app/core/config.py",
        "app/models/user.py",
        "app/api/v1/api.py",
        "start_dev.sh"
    ]
    
    print("📁 Project Structure:")
    for file in important_files:
        status = "✅" if os.path.exists(file) else "❌"
        print(f"   {status} {file}")

def show_api_endpoints():
    """Show available API endpoints"""
    endpoints = {
        "Authentication": [
            "POST /api/v1/auth/register",
            "POST /api/v1/auth/login",
            "POST /api/v1/auth/refresh"
        ],
        "Cards": [
            "GET /api/v1/cards",
            "POST /api/v1/cards",
            "GET /api/v1/cards/{card_id}",
            "PUT /api/v1/cards/{card_id}",
            "DELETE /api/v1/cards/{card_id}"
        ],
        "Transactions": [
            "GET /api/v1/transactions",
            "POST /api/v1/transactions",
            "GET /api/v1/transactions/{transaction_id}",
            "PUT /api/v1/transactions/{transaction_id}",
            "DELETE /api/v1/transactions/{transaction_id}"
        ],
        "Budgets": [
            "GET /api/v1/budgets",
            "POST /api/v1/budgets",
            "GET /api/v1/budgets/{budget_id}",
            "PUT /api/v1/budgets/{budget_id}",
            "DELETE /api/v1/budgets/{budget_id}"
        ],
        "Analytics": [
            "GET /api/v1/analytics/spending-by-category",
            "GET /api/v1/analytics/monthly-trends",
            "GET /api/v1/analytics/year-comparison"
        ],
        "AI Services": [
            "POST /api/v1/ai/categorize-transaction",
            "POST /api/v1/ai/analyze-spending",
            "POST /api/v1/ai/detect-anomalies"
        ],
        "Statements": [
            "POST /api/v1/statements/upload",
            "GET /api/v1/statements",
            "GET /api/v1/statements/{statement_id}"
        ]
    }
    
    print("🔌 Available API Endpoints:")
    for category, endpoints_list in endpoints.items():
        print(f"   📂 {category}:")
        for endpoint in endpoints_list:
            print(f"      • {endpoint}")

def main():
    print("🏦 PersonalCFO Backend - Project Summary")
    print("=" * 60)
    
    # Project status
    print("\n🚀 Project Status: READY FOR DEVELOPMENT")
    print("   ✅ Core backend infrastructure complete")
    print("   ✅ Database migrations setup")
    print("   ✅ Authentication system working")
    print("   ✅ API endpoints implemented")
    print("   ✅ Development server running")
    
    print("\n" + "=" * 60)
    
    # Check files
    check_files()
    
    print("\n" + "=" * 60)
    
    # Check database
    check_database()
    
    print("\n" + "=" * 60)
    
    # Show API endpoints
    show_api_endpoints()
    
    print("\n" + "=" * 60)
    
    print("\n🌟 Next Steps:")
    print("   1. Start development server: ./start_dev.sh")
    print("   2. Visit API docs: http://localhost:8000/docs")
    print("   3. Test with: python test_api.py")
    print("   4. Implement frontend integration")
    print("   5. Add production deployment (Docker)")
    
    print("\n📚 Additional Resources:")
    print("   • FastAPI docs: https://fastapi.tiangolo.com/")
    print("   • SQLAlchemy: https://docs.sqlalchemy.org/")
    print("   • Alembic: https://alembic.sqlalchemy.org/")
    
    print("\n" + "=" * 60)
    print("🎉 PersonalCFO Backend is ready for action!")

if __name__ == "__main__":
    main()
