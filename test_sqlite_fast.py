#!/usr/bin/env python3
"""
Simple test to verify SQLite fast processing works
"""

import requests
import json
import os

BASE_URL = "http://localhost:8000/api/v1"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpassword123"

def test_fast_processing():
    print("🧪 Testing Fast Processing with SQLite")
    print("=" * 40)
    
    # 1. Login
    print("1. 🔐 Logging in...")
    login_data = {"email": TEST_EMAIL, "password": TEST_PASSWORD}
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    
    if response.status_code != 200:
        print(f"   ❌ Login failed: {response.text}")
        return False
    
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("   ✅ Login successful")
    
    # 2. Check if we have statements
    print("2. 📋 Checking existing statements...")
    response = requests.get(f"{BASE_URL}/statements", headers=headers)
    
    if response.status_code == 200:
        statements = response.json()
        print(f"   ✅ Found {len(statements)} statements")
        
        if statements:
            # Use the first statement for testing
            statement_id = statements[0]["id"]
            print(f"   📄 Using statement: {statement_id}")
            
            # 3. Check if we have cards
            print("3. 💳 Checking cards...")
            response = requests.get(f"{BASE_URL}/cards", headers=headers)
            
            if response.status_code == 200:
                cards = response.json()
                print(f"   ✅ Found {len(cards)} cards")
                
                if cards:
                    card_name = cards[0]["card_name"]
                    print(f"   💳 Using card: {card_name}")
                    
                    # 4. Test fast processing
                    print("4. ⚡ Testing fast processing...")
                    process_data = {
                        "card_name": card_name,
                        "statement_month": "2025-01-01"
                    }
                    
                    response = requests.post(
                        f"{BASE_URL}/statements/{statement_id}/process-fast",
                        json=process_data,
                        headers=headers
                    )
                    
                    print(f"   Response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        result = response.json()
                        print("   ✅ Fast processing successful!")
                        print(f"   📊 Result: {json.dumps(result, indent=2)}")
                        return True
                    else:
                        print(f"   ❌ Fast processing failed: {response.text}")
                        return False
                else:
                    print("   ❌ No cards found")
                    return False
            else:
                print(f"   ❌ Failed to get cards: {response.text}")
                return False
        else:
            print("   ❌ No statements found")
            return False
    else:
        print(f"   ❌ Failed to get statements: {response.text}")
        return False

if __name__ == "__main__":
    try:
        success = test_fast_processing()
        if success:
            print("\n🎉 SQLite Fast Processing Test PASSED!")
        else:
            print("\n❌ SQLite Fast Processing Test FAILED!")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
