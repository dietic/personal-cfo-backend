#!/usr/bin/env python3
"""
Simple test for enhanced PDF functionality
"""

import requests
import json
import os

# Configuration
BASE_URL = "http://localhost:8000/api/v1"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpassword123"

def test_simple_pdf():
    print("🔥 Simple PDF Test")
    print("=" * 30)
    
    # Step 1: Register/Login
    print("1. 🔐 Setting up user...")
    
    # Try to register first
    register_data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
    if response.status_code == 200:
        print("   ✅ User registered")
    else:
        print("   ℹ️  User already exists, proceeding with login")
    
    # Login
    login_data = {
        "username": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    response = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    if response.status_code != 200:
        print(f"   ❌ Login failed: {response.text}")
        return False
    
    token_data = response.json()
    access_token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    print("   ✅ User authenticated")
    
    # Step 2: Create a card
    print("2. 💳 Creating card...")
    
    card_data = {
        "card_name": "Test PDF Card",
        "payment_due_date": "2025-06-15",
        "network_provider": "VISA",
        "bank_provider": "Test Bank",
        "card_type": "credit"
    }
    
    response = requests.post(f"{BASE_URL}/cards", json=card_data, headers=headers)
    if response.status_code != 200:
        print(f"   ❌ Card creation failed: {response.text}")
        return False
    
    card = response.json()
    print(f"   ✅ Card created: {card['card_name']}")
    
    # Step 3: Test PDF upload (only PDF allowed)
    print("3. 📄 Testing PDF upload...")
    
    pdf_path = "/Users/diego/Documents/Proyectos/personal-cfo/personal-cfo-backend/EECC_VISA_unlocked.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"   ❌ PDF not found: {pdf_path}")
        return False
    
    with open(pdf_path, "rb") as f:
        files = {"file": ("test_statement.pdf", f, "application/pdf")}
        response = requests.post(f"{BASE_URL}/statements/upload", files=files, headers=headers)
    
    if response.status_code != 200:
        print(f"   ❌ PDF upload failed: {response.text}")
        return False
    
    statement = response.json()
    statement_id = statement["id"]
    print(f"   ✅ PDF uploaded: {statement['filename']}")
    
    # Step 4: Test CSV rejection
    print("4. ❌ Testing CSV rejection...")
    
    # Create a temporary CSV content
    csv_content = "date,merchant,amount\n2025-06-01,Test Store,50.00\n"
    
    files = {"file": ("test.csv", csv_content, "text/csv")}
    response = requests.post(f"{BASE_URL}/statements/upload", files=files, headers=headers)
    
    if response.status_code == 400:
        print("   ✅ CSV correctly rejected (PDF only)")
    else:
        print(f"   ❌ CSV should have been rejected: {response.status_code}")
    
    # Step 5: Test basic processing (without full AI for now)
    print("5. 🤖 Testing statement processing...")
    
    process_data = {
        "card_name": card["card_name"]
    }
    
    response = requests.post(
        f"{BASE_URL}/statements/{statement_id}/process",
        json=process_data,
        headers=headers
    )
    
    if response.status_code == 200:
        result = response.json()
        print("   ✅ Statement processed successfully")
        print(f"      - Transactions found: {result.get('transactions_found', 0)}")
        print(f"      - Transactions created: {result.get('transactions_created', 0)}")
        print(f"      - Alerts created: {result.get('alerts_created', 0)}")
        return True
    else:
        print(f"   ❌ Processing failed: {response.text}")
        return False

if __name__ == "__main__":
    try:
        success = test_simple_pdf()
        if success:
            print("\n🎉 Simple PDF test completed successfully!")
        else:
            print("\n❌ Test failed")
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
