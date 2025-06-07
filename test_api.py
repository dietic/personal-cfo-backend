"""
API Test Suite for PersonalCFO Backend
"""
import requests
import json
import os

BASE_URL = "http://localhost:8000"

def test_health_check():
    """Test the health check endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        print(f"Health Check: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_user_registration():
    """Test user registration"""
    user_data = {
        "email": "testuser@example.com",
        "password": "testpassword123"
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/auth/register", json=user_data)
    print(f"User Registration: {response.status_code}")
    if response.status_code == 200:
        user = response.json()
        print(f"Created user: {user['email']} (ID: {user['id']})")
        return user
    else:
        print(f"Registration failed: {response.text}")
        return None

def test_user_login(email, password):
    """Test user login"""
    login_data = {
        "email": email,
        "password": password
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data)
    print(f"User Login: {response.status_code}")
    if response.status_code == 200:
        token_data = response.json()
        print(f"Login successful, token type: {token_data['token_type']}")
        return token_data["access_token"]
    else:
        print(f"Login failed: {response.text}")
        return None

def test_protected_endpoint(token):
    """Test accessing a protected endpoint"""
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(f"{BASE_URL}/api/v1/auth/refresh", headers=headers)
    print(f"Protected endpoint: {response.status_code}")
    if response.status_code == 200:
        print("Access to protected endpoint successful")
        return True
    else:
        print(f"Protected endpoint failed: {response.text}")
        return False

def test_card_creation(token):
    """Test card creation"""
    headers = {"Authorization": f"Bearer {token}"}
    card_data = {
        "card_name": "Test Credit Card",
        "network_provider": "VISA",
        "bank_provider": "Test Bank",
        "card_type": "credit",
        "payment_due_date": "2025-07-15"
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/cards", json=card_data, headers=headers)
    print(f"Card Creation: {response.status_code}")
    if response.status_code == 200:
        card = response.json()
        print(f"Created card: {card['card_name']} (ID: {card['id']})")
        return card
    else:
        print(f"Card creation failed: {response.text}")
        return None

def run_tests():
    """Run all tests"""
    print("🧪 PersonalCFO API Test Suite")
    print("=" * 50)
    
    # Test 1: Health Check
    if not test_health_check():
        print("❌ Health check failed - server might not be running")
        return
    
    # Test 2: User Registration
    user = test_user_registration()
    if not user:
        print("❌ User registration failed")
        return
    
    # Test 3: User Login
    token = test_user_login(user["email"], "testpassword123")
    if not token:
        print("❌ User login failed")
        return
    
    # Test 4: Protected Endpoint
    if not test_protected_endpoint(token):
        print("❌ Protected endpoint access failed")
        return
    
    # Test 5: Card Creation
    card = test_card_creation(token)
    if not card:
        print("❌ Card creation failed")
        return
    
    print("=" * 50)
    print("🎉 All tests passed! PersonalCFO API is working correctly.")

if __name__ == "__main__":
    run_tests()
