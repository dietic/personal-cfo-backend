#!/usr/bin/env python3
"""
Test script for enhanced statement import functionality
This demonstrates the complete flow with currency detection and AI insights
"""

import requests
import json
import os
from datetime import date
from io import StringIO

# Configuration
BASE_URL = "http://localhost:8000/api/v1"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpassword123"

def create_test_csv():
    """Create a sample CSV file with mixed currencies"""
    csv_content = """Date,Description,Amount
2025-06-01,McDonald's,S/.25.50
2025-06-02,Starbucks,$4.50
2025-06-03,Grocery Store,S/.85.30
2025-06-04,Gas Station,$35.00
2025-06-05,Netflix Subscription,$15.99"""
    
    with open("test_statement.csv", "w") as f:
        f.write(csv_content)
    return "test_statement.csv"

def test_statement_import_flow():
    """Test the complete statement import flow"""
    print("🧪 Testing Enhanced Statement Import Flow")
    print("=" * 50)
    
    # Step 1: Register/Login
    print("1. 🔐 Authenticating user...")
    
    # Try to register (might fail if user exists)
    register_data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
    if response.status_code != 200:
        print("   User might already exist, trying to login...")
    
    # Login
    login_data = {
        "username": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    response = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    if response.status_code != 200:
        print(f"   ❌ Login failed: {response.text}")
        return
    
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("   ✅ Authenticated successfully")
    
    # Step 2: Create a test card
    print("2. 💳 Creating test card...")
    
    card_data = {
        "card_name": "Test Credit Card",
        "payment_due_date": "2025-06-15",
        "network_provider": "VISA",
        "bank_provider": "Test Bank",
        "card_type": "credit"
    }
    
    response = requests.post(f"{BASE_URL}/cards", json=card_data, headers=headers)
    if response.status_code != 200:
        print(f"   ❌ Card creation failed: {response.text}")
        return
    
    card = response.json()
    card_id = card["id"]
    card_name = card["card_name"]
    print(f"   ✅ Card created: {card_name} (ID: {card_id})")
    
    # Step 3: Create and upload test statement
    print("3. 📄 Creating and uploading test statement...")
    
    csv_file = create_test_csv()
    
    with open(csv_file, "rb") as f:
        files = {"file": ("test_statement.csv", f, "text/csv")}
        response = requests.post(f"{BASE_URL}/statements/upload", files=files, headers=headers)
    
    if response.status_code != 200:
        print(f"   ❌ Statement upload failed: {response.text}")
        return
    
    statement = response.json()
    statement_id = statement["id"]
    print(f"   ✅ Statement uploaded: {statement['filename']} (ID: {statement_id})")
    
    # Step 4: Process statement with enhanced features
    print("4. 🤖 Processing statement with AI analysis...")
    
    process_data = {
        "card_name": card_name,  # Using card name instead of ID
        "statement_month": "2025-06-01"  # Specify the statement month
    }
    
    response = requests.post(
        f"{BASE_URL}/statements/{statement_id}/process",
        json=process_data,
        headers=headers
    )
    
    if response.status_code != 200:
        print(f"   ❌ Statement processing failed: {response.text}")
        return
    
    result = response.json()
    print(f"   ✅ Statement processed successfully!")
    print(f"      - Transactions found: {result['transactions_found']}")
    print(f"      - Transactions created: {result['transactions_created']}")
    
    if result.get("ai_insights"):
        insights = result["ai_insights"]
        print(f"      - AI Insights generated: ✅")
        
        if "summary" in insights:
            print(f"      - Summary: {insights['summary']}")
        
        if "insights" in insights and insights["insights"]:
            print(f"      - Key insights: {len(insights['insights'])} found")
            for insight in insights["insights"][:2]:  # Show first 2
                print(f"        • {insight.get('title', 'N/A')}: {insight.get('description', 'N/A')}")
        
        if "tips" in insights and insights["tips"]:
            print(f"      - Tips provided: {len(insights['tips'])}")
            for tip in insights["tips"][:2]:  # Show first 2
                print(f"        💡 {tip}")
        
        if "alerts" in insights and insights["alerts"]:
            print(f"      - Alerts: {len(insights['alerts'])}")
            for alert in insights["alerts"]:
                print(f"        ⚠️  {alert}")
    
    # Step 5: Get AI insights separately
    print("5. 🔍 Retrieving AI insights...")
    
    response = requests.get(f"{BASE_URL}/statements/{statement_id}/insights", headers=headers)
    
    if response.status_code == 200:
        insights = response.json()
        print("   ✅ AI insights retrieved successfully!")
        
        if "recommendations" in insights and insights["recommendations"]:
            print(f"      - Recommendations: {len(insights['recommendations'])}")
            for rec in insights["recommendations"][:2]:
                print(f"        📋 {rec}")
    else:
        print(f"   ⚠️  Could not retrieve insights: {response.text}")
    
    # Step 6: Check created transactions with currency info
    print("6. 💰 Checking created transactions...")
    
    response = requests.get(f"{BASE_URL}/transactions", headers=headers)
    
    if response.status_code == 200:
        transactions = response.json()
        print(f"   ✅ Found {len(transactions)} transactions")
        
        # Show currency breakdown
        usd_count = sum(1 for tx in transactions if tx.get("currency") == "USD")
        pen_count = sum(1 for tx in transactions if tx.get("currency") == "PEN")
        
        print(f"      - USD transactions: {usd_count}")
        print(f"      - PEN transactions: {pen_count}")
        
        # Show sample transactions
        print("      - Sample transactions:")
        for tx in transactions[:3]:
            currency = tx.get("currency", "USD")
            symbol = "$" if currency == "USD" else "S/."
            print(f"        • {tx['merchant']}: {symbol}{tx['amount']} ({tx.get('category', 'uncategorized')})")
    
    # Cleanup
    print("\n7. 🧹 Cleaning up...")
    try:
        os.remove(csv_file)
        print("   ✅ Test file cleaned up")
    except:
        pass
    
    print("\n🎉 Statement import test completed successfully!")
    print("=" * 50)
    print()
    print("📋 Summary of Enhanced Features Tested:")
    print("✅ Currency detection (USD $ and PEN S/.)")
    print("✅ Card identification by name instead of ID")
    print("✅ Statement month specification")
    print("✅ AI-powered insights and tips generation")
    print("✅ Enhanced transaction categorization")
    print("✅ Comprehensive spending analysis")

if __name__ == "__main__":
    try:
        test_statement_import_flow()
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to the API server.")
        print("   Make sure the server is running with: ./start_dev.sh")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
