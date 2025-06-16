#!/usr/bin/env python3

import requests
import json

def get_auth_token():
    """Get authentication token"""
    login_data = {
        "email": "dierios93@gmail.com",
        "password": "Lima2023$"
    }
    
    response = requests.post("http://localhost:8000/api/v1/auth/login", json=login_data)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"Login failed: {response.text}")

def get_categories(token):
    """Get user categories"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get("http://localhost:8000/api/v1/categories/", headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get categories: {response.text}")

def add_keyword(token, category_id, keyword):
    """Add a keyword to a category"""
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "keyword": keyword,
        "category_id": category_id,
        "description": f"Additional keyword to reach 15 per category"
    }
    
    response = requests.post("http://localhost:8000/api/v1/keywords/", headers=headers, json=data)
    return response.status_code == 200

def main():
    """Add missing keywords to reach 15 per category"""
    
    print("Starting keyword addition process...")
    
    # Additional keywords to reach 15 per category
    additional_keywords = {
        'Food & Dining': ['takeout', 'delivery', 'fastfood'],  # Currently has 12, need 3 more
        'Transportation': ['rideshare', 'bicycle', 'motorcycle'],  # Currently has 12, need 3 more
        'Shopping': ['boutique', 'outlet', 'thrift', 'consignment', 'vintage', 'department'],  # Currently has 9, need 6 more
        'Entertainment': ['gaming', 'books', 'magazines', 'sports', 'events'],  # Currently has 10, need 5 more
        'Utilities': ['trash', 'recycling', 'security', 'alarm', 'maintenance'],  # Currently has 10, need 5 more
        'Healthcare': ['checkup', 'specialist', 'lab', 'radiology', 'physical', 'mental'],  # Currently has 9, need 6 more
        'Housing': ['utilities', 'taxes', 'association', 'security', 'cleaning', 'landscaping']  # Currently has 9, need 6 more
    }
    
    try:
        print("Getting authentication token...")
        token = get_auth_token()
        print("Token obtained successfully")
        
        print("Fetching categories...")
        categories = get_categories(token)
        print(f"Found {len(categories)} categories")
        
        for category in categories:
            category_name = category['name']
            current_keywords = category['keywords']
            print(f"\n{category_name}: {len(current_keywords)} keywords")
            
            if category_name in additional_keywords:
                new_keywords = additional_keywords[category_name]
                print(f"  Adding {len(new_keywords)} new keywords: {new_keywords}")
                
                for keyword in new_keywords:
                    if keyword not in current_keywords:
                        success = add_keyword(token, category['id'], keyword)
                        if success:
                            print(f"    ✓ Added: {keyword}")
                        else:
                            print(f"    ✗ Failed to add: {keyword}")
                    else:
                        print(f"    - Already exists: {keyword}")
            else:
                print(f"  No additional keywords defined for {category_name}")
        
        print("\nCompleted adding keywords!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    main()
