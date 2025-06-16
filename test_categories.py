#!/usr/bin/env python3

import requests
import json
import traceback

print("Starting test...")

# Get authentication token
login_data = {
    "email": "dierios93@gmail.com",
    "password": "Lima2023$"
}

try:
    print("Attempting login...")
    # Login
    response = requests.post("http://localhost:8000/api/v1/auth/login", json=login_data, timeout=10)
    print(f"Login status: {response.status_code}")
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        print(f"Token received: {token[:50]}...")
        
        print("Testing categories endpoint...")
        # Test categories endpoint
        headers = {"Authorization": f"Bearer {token}"}
        categories_response = requests.get("http://localhost:8000/api/v1/categories/", headers=headers, timeout=10)
        
        print(f"Categories status: {categories_response.status_code}")
        print(f"Categories response: {categories_response.text[:500]}")
        
        if categories_response.status_code == 200:
            categories = categories_response.json()
            print(f"Number of categories: {len(categories)}")
            for cat in categories[:3]:  # Show first 3
                print(f"  - {cat['name']} (id: {cat['id']})")
        else:
            print(f"Categories error: {categories_response.text}")
    else:
        print(f"Login error: {response.text}")

except Exception as e:
    print(f"Error: {e}")
    print(f"Traceback: {traceback.format_exc()}")

print("Test completed.")
