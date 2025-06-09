#!/usr/bin/env python3
"""
Enhanced Statement Processing System Test
Tests the complete workflow:
1. Category management with minimum requirements
2. Separate extraction and categorization
3. Keyword-based and AI categorization
4. Status polling and retry functionality
"""

import sys
import os
import requests
import json
import time
from pathlib import Path

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent))

API_BASE = "http://localhost:8000/api/v1"

class TestEnhancedStatementProcessing:
    def __init__(self):
        self.token = None
        self.user_data = {
            "email": "test_enhanced@example.com",
            "password": "testpassword123",
            "first_name": "Enhanced",
            "last_name": "Tester"
        }
        self.statement_id = None
        self.card_id = None
        
    def setup_auth(self):
        """Register and authenticate user"""
        print("🔐 Setting up authentication...")
        
        # Register user
        response = requests.post(f"{API_BASE}/auth/register", json=self.user_data)
        if response.status_code not in [200, 400]:  # 400 if user already exists
            print(f"❌ Registration failed: {response.text}")
            return False
            
        # Login
        login_data = {
            "username": self.user_data["email"],
            "password": self.user_data["password"]
        }
        response = requests.post(f"{API_BASE}/auth/login", data=login_data)
        if response.status_code != 200:
            print(f"❌ Login failed: {response.text}")
            return False
            
        self.token = response.json()["access_token"]
        print("✅ Authentication successful")
        return True
        
    def get_headers(self):
        """Get authorization headers"""
        return {"Authorization": f"Bearer {self.token}"}
        
    def test_category_requirements(self):
        """Test category management and minimum requirements"""
        print("\n📊 Testing category management...")
        
        # Check initial category count (should be 0 for new user)
        response = requests.get(f"{API_BASE}/categories/validate-minimum", headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Failed to check category requirements: {response.text}")
            return False
            
        data = response.json()
        print(f"Initial categories: {data['current_count']}/{data['minimum_required']}")
        
        # Try to check statement upload requirements (should fail)
        response = requests.get(f"{API_BASE}/statements/check-categories", headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Failed to check statement requirements: {response.text}")
            return False
            
        data = response.json()
        if data["can_upload"]:
            print("⚠️  User can upload statements before having minimum categories")
        else:
            print("✅ Correctly blocking statement upload until minimum categories")
            
        # Create default categories
        print("Creating default categories...")
        response = requests.post(f"{API_BASE}/categories/create-defaults", headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Failed to create default categories: {response.text}")
            return False
            
        categories = response.json()
        print(f"✅ Created {len(categories)} default categories")
        
        # Verify we can now upload statements
        response = requests.get(f"{API_BASE}/statements/check-categories", headers=self.get_headers())
        data = response.json()
        if not data["can_upload"]:
            print(f"❌ Still can't upload statements: {data['message']}")
            return False
            
        print("✅ Can now upload statements")
        
        # Test creating a custom category with keywords
        custom_category = {
            "name": "Online Services",
            "color": "#FF5733",
            "keywords": ["amazon", "netflix", "spotify", "digital", "subscription", "online"]
        }
        
        response = requests.post(f"{API_BASE}/categories/", json=custom_category, headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Failed to create custom category: {response.text}")
            return False
            
        print("✅ Created custom category with keywords")
        
        # Test keyword matching
        response = requests.post(
            f"{API_BASE}/categories/test-keywords",
            params={"merchant": "Amazon Prime", "description": "Monthly subscription"},
            headers=self.get_headers()
        )
        
        if response.status_code != 200:
            print(f"❌ Keyword test failed: {response.text}")
            return False
            
        match_data = response.json()
        if match_data["match_found"]:
            print(f"✅ Keyword matching works: {match_data['category']} (confidence: {match_data['confidence']})")
        else:
            print("⚠️  No keyword match found for test")
            
        return True
        
    def test_statement_upload_validation(self):
        """Test statement upload with category validation"""
        print("\n📄 Testing statement upload with validation...")
        
        # Create a test card first
        card_data = {
            "card_name": "Test Enhanced Card",
            "card_type": "credit",
            "bank_provider": "Test Bank",
            "payment_due_date": "2025-06-15"
        }
        
        response = requests.post(f"{API_BASE}/cards/", json=card_data, headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Failed to create card: {response.text}")
            return False
            
        self.card_id = response.json()["id"]
        print("✅ Created test card")
        
        # Try to upload a statement (will use test PDF if available)
        pdf_files = list(Path(".").glob("*.pdf"))
        if not pdf_files:
            print("⚠️  No PDF files found for testing upload")
            return True
            
        pdf_file = pdf_files[0]
        print(f"Uploading {pdf_file.name}...")
        
        with open(pdf_file, 'rb') as f:
            files = {'file': (pdf_file.name, f, 'application/pdf')}
            response = requests.post(
                f"{API_BASE}/statements/upload",
                files=files,
                headers=self.get_headers()
            )
            
        if response.status_code != 200:
            print(f"❌ Statement upload failed: {response.text}")
            return False
            
        statement_data = response.json()
        self.statement_id = statement_data["id"]
        print(f"✅ Statement uploaded successfully: {self.statement_id}")
        
        return True
        
    def test_extraction_step(self):
        """Test separate transaction extraction"""
        print("\n🔍 Testing transaction extraction...")
        
        if not self.statement_id:
            print("❌ No statement ID available for extraction")
            return False
            
        # Test extraction
        extraction_request = {
            "card_id": self.card_id,
            "statement_month": "2025-06-01"
        }
        
        response = requests.post(
            f"{API_BASE}/statements/{self.statement_id}/extract",
            json=extraction_request,
            headers=self.get_headers()
        )
        
        if response.status_code != 200:
            print(f"❌ Extraction failed: {response.text}")
            return False
            
        result = response.json()
        print(f"✅ Extraction successful: {result['transactions_found']} transactions found")
        
        # Check status after extraction
        response = requests.get(
            f"{API_BASE}/statements/{self.statement_id}/status",
            headers=self.get_headers()
        )
        
        if response.status_code == 200:
            status = response.json()
            print(f"Status: {status['status']}, Progress: {status['progress_percentage']}%")
            print(f"Current step: {status['current_step']}")
        
        return True
        
    def test_categorization_step(self):
        """Test separate transaction categorization"""
        print("\n🏷️  Testing transaction categorization...")
        
        if not self.statement_id:
            print("❌ No statement ID available for categorization")
            return False
            
        # Test categorization with both AI and keywords
        categorization_request = {
            "use_ai": True,
            "use_keywords": True
        }
        
        response = requests.post(
            f"{API_BASE}/statements/{self.statement_id}/categorize",
            json=categorization_request,
            headers=self.get_headers()
        )
        
        if response.status_code != 200:
            print(f"❌ Categorization failed: {response.text}")
            return False
            
        result = response.json()
        print(f"✅ Categorization successful:")
        print(f"  - Total transactions: {result['transactions_categorized']}")
        print(f"  - AI categorized: {result['ai_categorized']}")
        print(f"  - Keyword categorized: {result['keyword_categorized']}")
        print(f"  - Uncategorized: {result['uncategorized']}")
        
        # Check final status
        response = requests.get(
            f"{API_BASE}/statements/{self.statement_id}/status",
            headers=self.get_headers()
        )
        
        if response.status_code == 200:
            status = response.json()
            print(f"Final status: {status['status']}, Progress: {status['progress_percentage']}%")
        
        return True
        
    def test_status_polling(self):
        """Test status polling functionality"""
        print("\n📊 Testing status polling...")
        
        if not self.statement_id:
            print("❌ No statement ID available for status polling")
            return False
            
        response = requests.get(
            f"{API_BASE}/statements/{self.statement_id}/status",
            headers=self.get_headers()
        )
        
        if response.status_code != 200:
            print(f"❌ Status polling failed: {response.text}")
            return False
            
        status = response.json()
        print("✅ Status polling working:")
        print(f"  - Overall status: {status['status']}")
        print(f"  - Extraction status: {status['extraction_status']}")
        print(f"  - Categorization status: {status['categorization_status']}")
        print(f"  - Progress: {status['progress_percentage']}%")
        print(f"  - Current step: {status['current_step']}")
        print(f"  - Retry counts: {status['retry_count']}")
        
        return True
        
    def test_categorization_suggestions(self):
        """Test categorization suggestions"""
        print("\n💡 Testing categorization suggestions...")
        
        # Test suggestion for a known merchant
        response = requests.get(
            f"{API_BASE}/categories/suggest/Amazon",
            params={"description": "Online purchase", "amount": 25.99},
            headers=self.get_headers()
        )
        
        if response.status_code != 200:
            print(f"❌ Suggestion test failed: {response.text}")
            return False
            
        suggestions = response.json()
        print(f"✅ Got {len(suggestions['suggestions'])} suggestions for Amazon:")
        for suggestion in suggestions["suggestions"]:
            print(f"  - {suggestion['category']} (confidence: {suggestion['confidence']:.2f}, method: {suggestion['method']})")
            
        return True
        
    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting Enhanced Statement Processing System Tests\n")
        
        if not self.setup_auth():
            return False
            
        tests = [
            ("Category Management", self.test_category_requirements),
            ("Statement Upload Validation", self.test_statement_upload_validation),
            ("Transaction Extraction", self.test_extraction_step),
            ("Transaction Categorization", self.test_categorization_step),
            ("Status Polling", self.test_status_polling),
            ("Categorization Suggestions", self.test_categorization_suggestions),
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            try:
                if test_func():
                    passed += 1
                    print(f"✅ {test_name} PASSED")
                else:
                    print(f"❌ {test_name} FAILED")
            except Exception as e:
                print(f"❌ {test_name} ERROR: {str(e)}")
                
        print(f"\n📊 Test Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! Enhanced statement processing system is working correctly.")
            return True
        else:
            print(f"⚠️  {total - passed} tests failed. Check the output above for details.")
            return False


if __name__ == "__main__":
    # Check if server is running
    try:
        response = requests.get(f"{API_BASE}/", timeout=5)
    except requests.exceptions.RequestException:
        print("❌ Server is not running. Please start the server with:")
        print("   python main.py")
        sys.exit(1)
        
    tester = TestEnhancedStatementProcessing()
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)
