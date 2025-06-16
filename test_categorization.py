#!/usr/bin/env python3

import requests
import json

def test_keyword_categorization():
    """Test the keyword-based categorization functionality"""
    
    print("Starting keyword categorization test...")
    
    # Get authentication token
    login_data = {
        "email": "dierios93@gmail.com",
        "password": "Lima2023$"
    }
    
    print("Attempting login...")
    response = requests.post("http://localhost:8000/api/v1/auth/login", json=login_data)
    if response.status_code != 200:
        print(f"Login failed: {response.text}")
        return
    
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Login successful!")
    
    # Test transactions that should match our keywords
    test_transactions = [
        {"description": "McDonald's Restaurant", "expected_category": "Food & Dining"},
        {"description": "Netflix Subscription", "expected_category": "Entertainment"},
        {"description": "Shell Gas Station", "expected_category": "Transportation"},
        {"description": "Amazon.com Purchase", "expected_category": "Shopping"},
        {"description": "Doctor Visit Copay", "expected_category": "Healthcare"},
        {"description": "Rent Payment", "expected_category": "Housing"},
        {"description": "Electric Bill Payment", "expected_category": "Utilities"},
    ]
    
    print("Testing keyword-based categorization:")
    print("-" * 50)
    
    # Get categories for reference
    categories_response = requests.get("http://localhost:8000/api/v1/categories/", headers=headers)
    if categories_response.status_code == 200:
        categories = {cat['name']: cat['id'] for cat in categories_response.json()}
        print(f"Available categories: {list(categories.keys())}")
        print()
    else:
        print(f"Failed to get categories: {categories_response.text}")
        return
    
    # Test each transaction
    for transaction in test_transactions:
        test_url = f"http://localhost:8000/api/v1/categories/test-keywords"
        params = {
            "merchant": transaction["description"],
            "description": transaction["description"]
        }
        
        response = requests.post(test_url, headers=headers, params=params)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("match_found"):
                matched_category = result.get("category", "Unknown")
                confidence = result.get("confidence", 0)
                keywords_matched = result.get("matched_keywords", [])
                
                status = "✓" if matched_category == transaction["expected_category"] else "✗"
                print(f"{status} {transaction['description']}")
                print(f"   Expected: {transaction['expected_category']}")
                print(f"   Matched: {matched_category} (confidence: {confidence:.2f})")
                print(f"   Keywords: {', '.join(keywords_matched)}")
            else:
                print(f"✗ {transaction['description']}")
                print(f"   Expected: {transaction['expected_category']}")
                print(f"   Matched: No match found")
                print(f"   Message: {result.get('message', 'Unknown error')}")
        else:
            print(f"✗ {transaction['description']}")
            print(f"   Expected: {transaction['expected_category']}")
            print(f"   Error: {response.text}")
        
        print()

if __name__ == "__main__":
    test_keyword_categorization()
