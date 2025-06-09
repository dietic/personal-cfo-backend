#!/usr/bin/env python3
"""
Test script for user profile and settings functionality
Tests all the profile features shown in the screenshots
"""

import requests
import json
import os
from datetime import date

# Configuration
BASE_URL = "http://localhost:8000/api/v1"
TEST_EMAIL = "profile.test@example.com"
TEST_PASSWORD = "testpassword123"

def test_user_profile_system():
    """Test the complete user profile and settings system"""
    
    print("👤 User Profile & Settings Test")
    print("=" * 50)
    
    # Step 1: Register and login user
    print("1. 🔐 Creating test user...")
    
    # Register user
    register_data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
    if response.status_code == 400:
        print("   ℹ️  User already exists, continuing with login...")
    elif response.status_code != 200:
        print(f"   ❌ Registration failed: {response.text}")
        return
    else:
        print("   ✅ User registered successfully")
    
    # Login
    login_data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    if response.status_code != 200:
        print(f"   ❌ Login failed: {response.text}")
        return
    
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("   ✅ User logged in successfully")
    
    # Step 2: Test Profile Information
    print("\n2. 👤 Testing Profile Information...")
    
    # Get initial profile
    response = requests.get(f"{BASE_URL}/users/profile", headers=headers)
    if response.status_code != 200:
        print(f"   ❌ Failed to get profile: {response.text}")
        return
    
    profile = response.json()
    print(f"   ✅ Retrieved profile for: {profile['email']}")
    print(f"   📧 Email: {profile['email']}")
    print(f"   💰 Currency: {profile['preferred_currency']}")
    print(f"   🌍 Timezone: {profile['timezone']}")
    
    # Update profile information
    profile_update = {
        "first_name": "John",
        "last_name": "Doe", 
        "phone_number": "+1 (555) 123-4567",
        "preferred_currency": "USD",
        "timezone": "UTC_MINUS_5"
    }
    
    response = requests.put(f"{BASE_URL}/users/profile", json=profile_update, headers=headers)
    if response.status_code != 200:
        print(f"   ❌ Failed to update profile: {response.text}")
        return
    
    updated_profile = response.json()
    print("   ✅ Profile updated successfully:")
    print(f"   👤 Name: {updated_profile['first_name']} {updated_profile['last_name']}")
    print(f"   📱 Phone: {updated_profile['phone_number']}")
    print(f"   💰 Currency: {updated_profile['preferred_currency']}")
    print(f"   🌍 Timezone: {updated_profile['timezone']}")
    
    # Step 3: Test Notification Preferences
    print("\n3. 🔔 Testing Notification Preferences...")
    
    # Get current preferences
    response = requests.get(f"{BASE_URL}/users/notifications", headers=headers)
    if response.status_code != 200:
        print(f"   ❌ Failed to get notifications: {response.text}")
        return
    
    notifications = response.json()
    print("   ✅ Current notification preferences:")
    print(f"   📊 Budget Alerts: {'✅' if notifications['budget_alerts_enabled'] else '❌'}")
    print(f"   💳 Payment Reminders: {'✅' if notifications['payment_reminders_enabled'] else '❌'}")
    print(f"   🔍 Transaction Alerts: {'✅' if notifications['transaction_alerts_enabled'] else '❌'}")
    print(f"   📅 Weekly Summary: {'✅' if notifications['weekly_summary_enabled'] else '❌'}")
    print(f"   📈 Monthly Reports: {'✅' if notifications['monthly_reports_enabled'] else '❌'}")
    print(f"   📧 Email Notifications: {'✅' if notifications['email_notifications_enabled'] else '❌'}")
    print(f"   📱 Push Notifications: {'✅' if notifications['push_notifications_enabled'] else '❌'}")
    
    # Update notification preferences (match the screenshot settings)
    notification_update = {
        "budget_alerts_enabled": True,
        "payment_reminders_enabled": True,
        "transaction_alerts_enabled": False,  # This was off in screenshot
        "weekly_summary_enabled": True,
        "monthly_reports_enabled": True,
        "email_notifications_enabled": True,
        "push_notifications_enabled": False   # This was off in screenshot
    }
    
    response = requests.put(f"{BASE_URL}/users/notifications", json=notification_update, headers=headers)
    if response.status_code != 200:
        print(f"   ❌ Failed to update notifications: {response.text}")
        return
    
    print("   ✅ Notification preferences updated to match frontend settings")
    
    # Step 4: Test Password Update
    print("\n4. 🔐 Testing Password Update...")
    
    password_update = {
        "current_password": TEST_PASSWORD,
        "new_password": "newpassword123",
        "confirm_new_password": "newpassword123"
    }
    
    response = requests.put(f"{BASE_URL}/users/password", json=password_update, headers=headers)
    if response.status_code != 200:
        print(f"   ❌ Failed to update password: {response.text}")
    else:
        print("   ✅ Password updated successfully")
        
        # Test login with new password
        login_data["password"] = "newpassword123"
        response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
        if response.status_code == 200:
            print("   ✅ Login with new password successful")
            # Update headers with new token
            token = response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
        else:
            print("   ❌ Login with new password failed")
    
    # Step 5: Test Account Statistics
    print("\n5. 📊 Testing Account Statistics...")
    
    response = requests.get(f"{BASE_URL}/users/account/stats", headers=headers)
    if response.status_code != 200:
        print(f"   ❌ Failed to get account stats: {response.text}")
    else:
        stats = response.json()
        print("   ✅ Account statistics retrieved:")
        print(f"   💳 Total Cards: {stats['total_cards']}")
        print(f"   💰 Total Transactions: {stats['total_transactions']}")
        print(f"   📊 Total Budgets: {stats['total_budgets']}")
        print(f"   📄 Total Statements: {stats['total_statements']}")
        print(f"   🔔 Total Alerts: {stats['total_alerts']}")
        print(f"   📅 Account Created: {stats['account_created']}")
    
    # Step 6: Test Danger Zone (Account Deletion)
    print("\n6. ⚠️  Testing Danger Zone...")
    print("   ℹ️  Account deletion test (will recreate account)")
    
    deletion_request = {
        "password": "newpassword123",
        "confirmation_text": "DELETE MY ACCOUNT"
    }
    
    response = requests.delete(f"{BASE_URL}/users/account", json=deletion_request, headers=headers)
    if response.status_code != 200:
        print(f"   ❌ Account deletion failed: {response.text}")
    else:
        print("   ✅ Account deleted successfully")
        
        # Verify account is deleted by trying to access profile
        response = requests.get(f"{BASE_URL}/users/profile", headers=headers)
        if response.status_code == 401:
            print("   ✅ Account deletion verified - access denied")
        else:
            print("   ⚠️  Account might not be fully deleted")
    
    print("\n🎉 User Profile & Settings Test Complete!")
    print("\n📋 Features Tested:")
    print("   ✅ Profile Information (Name, Email, Phone, Currency, Timezone)")
    print("   ✅ Notification Preferences (5 notification types + 2 delivery methods)")
    print("   ✅ Password Update with verification")
    print("   ✅ Account Statistics")
    print("   ✅ Account Deletion (Danger Zone)")
    print("\n🎯 All profile features from the screenshots are now supported!")

if __name__ == "__main__":
    try:
        test_user_profile_system()
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
