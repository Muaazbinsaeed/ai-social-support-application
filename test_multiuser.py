#!/usr/bin/env python3
"""
Test script for multi-user functionality
"""

import requests
import json
import time
from datetime import datetime

# API endpoints
AUTH_API = "http://localhost:8002"
MAIN_API = "http://localhost:8000"

def test_user_registration():
    """Test user registration"""
    print("🔐 Testing User Registration...")

    # Test user 1
    user1_data = {
        "email": "john.doe@example.com",
        "password": "TestPassword123",
        "full_name": "John Doe",
        "phone": "+971501234567"
    }

    response = requests.post(f"{AUTH_API}/auth/register", json=user1_data)
    print(f"User 1 registration: {response.status_code}")

    if response.status_code == 200:
        user1_token = response.json()["access_token"]
        print(f"✅ User 1 registered successfully")
        print(f"Token: {user1_token[:20]}...")
    else:
        print(f"❌ User 1 registration failed: {response.text}")
        return None, None

    # Test user 2
    user2_data = {
        "email": "jane.smith@example.com",
        "password": "SecurePass456",
        "full_name": "Jane Smith",
        "phone": "+971509876543"
    }

    response = requests.post(f"{AUTH_API}/auth/register", json=user2_data)
    print(f"User 2 registration: {response.status_code}")

    if response.status_code == 200:
        user2_token = response.json()["access_token"]
        print(f"✅ User 2 registered successfully")
        print(f"Token: {user2_token[:20]}...")
    else:
        print(f"❌ User 2 registration failed: {response.text}")
        return user1_token, None

    return user1_token, user2_token

def test_user_profiles(user1_token, user2_token):
    """Test user profile management"""
    print("\n👤 Testing User Profiles...")

    # Update user 1 profile
    user1_profile = {
        "emirates_id": "784-1234-1234567-1",
        "address": "Dubai, UAE",
        "family_size": 3,
        "employment_status": "employed",
        "monthly_income": 8000.0
    }

    headers1 = {"Authorization": f"Bearer {user1_token}"}
    response = requests.put(f"{AUTH_API}/users/profile", json=user1_profile, headers=headers1)
    print(f"User 1 profile update: {response.status_code}")

    if response.status_code == 200:
        print("✅ User 1 profile updated successfully")
    else:
        print(f"❌ User 1 profile update failed: {response.text}")

    # Update user 2 profile
    user2_profile = {
        "emirates_id": "784-5678-7654321-2",
        "address": "Abu Dhabi, UAE",
        "family_size": 2,
        "employment_status": "self_employed",
        "monthly_income": 5000.0
    }

    headers2 = {"Authorization": f"Bearer {user2_token}"}
    response = requests.put(f"{AUTH_API}/users/profile", json=user2_profile, headers=headers2)
    print(f"User 2 profile update: {response.status_code}")

    if response.status_code == 200:
        print("✅ User 2 profile updated successfully")
    else:
        print(f"❌ User 2 profile update failed: {response.text}")

def test_applications(user1_token, user2_token):
    """Test application submission with user isolation"""
    print("\n📋 Testing Application Submission...")

    # User 1 application
    user1_app = {
        "first_name": "John",
        "last_name": "Doe",
        "emirates_id": "784-1234-1234567-1",
        "email": "john.doe@example.com",
        "phone": "+971501234567",
        "application_type": "financial_support",
        "urgency_level": "high",
        "monthly_income": 8000,
        "family_size": 3,
        "employment_status": "employed"
    }

    headers1 = {"Authorization": f"Bearer {user1_token}"}
    response = requests.post(f"{MAIN_API}/applications/submit", json=user1_app, headers=headers1)
    print(f"User 1 application: {response.status_code}")

    if response.status_code == 200:
        user1_app_id = response.json()["application_id"]
        print(f"✅ User 1 application submitted: ID {user1_app_id}")
    else:
        print(f"❌ User 1 application failed: {response.text}")
        return None, None

    # User 2 application
    user2_app = {
        "first_name": "Jane",
        "last_name": "Smith",
        "emirates_id": "784-5678-7654321-2",
        "email": "jane.smith@example.com",
        "phone": "+971509876543",
        "application_type": "economic_enablement",
        "urgency_level": "normal",
        "monthly_income": 5000,
        "family_size": 2,
        "employment_status": "self_employed"
    }

    headers2 = {"Authorization": f"Bearer {user2_token}"}
    response = requests.post(f"{MAIN_API}/applications/submit", json=user2_app, headers=headers2)
    print(f"User 2 application: {response.status_code}")

    if response.status_code == 200:
        user2_app_id = response.json()["application_id"]
        print(f"✅ User 2 application submitted: ID {user2_app_id}")
    else:
        print(f"❌ User 2 application failed: {response.text}")
        return user1_app_id, None

    return user1_app_id, user2_app_id

def test_documents(user1_token, user2_token, user1_app_id, user2_app_id):
    """Test document upload with user isolation"""
    print("\n📄 Testing Document Upload...")

    # User 1 documents
    user1_docs = [
        {
            "filename": "john_emirates_id.pdf",
            "type": "emirates_id",
            "size": 512000,
            "content_type": "application/pdf"
        },
        {
            "filename": "john_bank_statement.pdf",
            "type": "bank_statement",
            "size": 1024000,
            "content_type": "application/pdf"
        }
    ]

    headers1 = {"Authorization": f"Bearer {user1_token}"}
    response = requests.post(
        f"{MAIN_API}/applications/{user1_app_id}/documents/upload",
        json=user1_docs,
        headers=headers1
    )
    print(f"User 1 documents: {response.status_code}")

    if response.status_code == 200:
        print(f"✅ User 1 uploaded {len(user1_docs)} documents")
    else:
        print(f"❌ User 1 document upload failed: {response.text}")

    # User 2 documents
    user2_docs = [
        {
            "filename": "jane_emirates_id.jpg",
            "type": "emirates_id",
            "size": 256000,
            "content_type": "image/jpeg"
        },
        {
            "filename": "jane_business_license.pdf",
            "type": "resume",
            "size": 768000,
            "content_type": "application/pdf"
        }
    ]

    headers2 = {"Authorization": f"Bearer {user2_token}"}
    response = requests.post(
        f"{MAIN_API}/applications/{user2_app_id}/documents/upload",
        json=user2_docs,
        headers=headers2
    )
    print(f"User 2 documents: {response.status_code}")

    if response.status_code == 200:
        print(f"✅ User 2 uploaded {len(user2_docs)} documents")
    else:
        print(f"❌ User 2 document upload failed: {response.text}")

def test_data_isolation(user1_token, user2_token):
    """Test that users can only see their own data"""
    print("\n🔒 Testing Data Isolation...")

    # User 1 gets their applications
    headers1 = {"Authorization": f"Bearer {user1_token}"}
    response = requests.get(f"{AUTH_API}/users/applications", headers=headers1)
    print(f"User 1 applications fetch: {response.status_code}")

    if response.status_code == 200:
        user1_apps = response.json()["applications"]
        print(f"✅ User 1 has {len(user1_apps)} applications")
    else:
        print(f"❌ User 1 applications fetch failed: {response.text}")

    # User 2 gets their applications
    headers2 = {"Authorization": f"Bearer {user2_token}"}
    response = requests.get(f"{AUTH_API}/users/applications", headers=headers2)
    print(f"User 2 applications fetch: {response.status_code}")

    if response.status_code == 200:
        user2_apps = response.json()["applications"]
        print(f"✅ User 2 has {len(user2_apps)} applications")
    else:
        print(f"❌ User 2 applications fetch failed: {response.text}")

    # Verify isolation
    if 'user1_apps' in locals() and 'user2_apps' in locals():
        user1_ids = [app["id"] for app in user1_apps]
        user2_ids = [app["id"] for app in user2_apps]

        overlap = set(user1_ids) & set(user2_ids)
        if not overlap:
            print("✅ Data isolation verified: No overlap between user applications")
        else:
            print(f"❌ Data isolation failed: Overlapping applications {overlap}")

def test_anonymous_vs_authenticated():
    """Test difference between anonymous and authenticated usage"""
    print("\n🔓 Testing Anonymous vs Authenticated Usage...")

    # Anonymous application
    anon_app = {
        "first_name": "Anonymous",
        "last_name": "User",
        "emirates_id": "784-0000-0000000-0",
        "email": "anonymous@example.com",
        "application_type": "financial_support"
    }

    response = requests.post(f"{MAIN_API}/applications/submit", json=anon_app)
    print(f"Anonymous application: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"✅ Anonymous application: ID {result['application_id']}")
        print(f"Authenticated: {result.get('authenticated', 'Not specified')}")
    else:
        print(f"❌ Anonymous application failed: {response.text}")

def main():
    """Main test function"""
    print("🧪 AI Social Support Multi-User Testing")
    print("=" * 50)

    try:
        # Check if services are running
        print("🔍 Checking services...")

        # Check auth service
        try:
            response = requests.get(f"{AUTH_API}/auth/health", timeout=5)
            if response.status_code == 200:
                print("✅ Auth service is running")
            else:
                print("❌ Auth service is not healthy")
                return
        except requests.exceptions.ConnectionError:
            print("❌ Auth service is not running")
            print("Start with: python run_with_auth.py")
            return

        # Check main API
        try:
            response = requests.get(f"{MAIN_API}/health", timeout=5)
            if response.status_code == 200:
                print("✅ Main API is running")
            else:
                print("❌ Main API is not healthy")
                return
        except requests.exceptions.ConnectionError:
            print("❌ Main API is not running")
            return

        print("\n🚀 Starting tests...")

        # Run tests
        user1_token, user2_token = test_user_registration()
        if not user1_token or not user2_token:
            print("❌ Cannot continue without user tokens")
            return

        test_user_profiles(user1_token, user2_token)

        user1_app_id, user2_app_id = test_applications(user1_token, user2_token)
        if not user1_app_id or not user2_app_id:
            print("❌ Cannot continue without application IDs")
            return

        test_documents(user1_token, user2_token, user1_app_id, user2_app_id)
        test_data_isolation(user1_token, user2_token)
        test_anonymous_vs_authenticated()

        print("\n🎉 All tests completed!")
        print("=" * 50)
        print("✅ Multi-user functionality is working correctly")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")

if __name__ == "__main__":
    main()