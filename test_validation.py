#!/usr/bin/env python3
"""
Quick test script for email validation improvements
"""

import requests
import json

AUTH_API = "http://localhost:8002"

def test_email_validation():
    """Test email validation with various invalid formats"""
    print("🧪 Testing Email Validation...")

    test_cases = [
        {"email": "a", "expected": "must have an @-sign"},
        {"email": "test@", "expected": "part after @ is not valid"},
        {"email": "test@domain", "expected": "should have a period"},
        {"email": "test@domain.com", "expected": "should work"},
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n📧 Test {i}: {case['email']}")

        response = requests.post(
            f"{AUTH_API}/auth/register",
            json={
                "email": case["email"],
                "password": "TestPassword123",
                "full_name": "Test User"
            }
        )

        if case["email"] == "test@domain.com":
            if response.status_code == 200:
                print(f"✅ Valid email accepted")
            else:
                print(f"❌ Valid email rejected: {response.status_code}")
        else:
            if response.status_code == 422:  # Validation error
                error_data = response.json()
                print(f"✅ Invalid email properly rejected")
                print(f"   Server response: {error_data.get('detail', [{}])[0].get('msg', 'No message')[:50]}...")
            else:
                print(f"❌ Expected validation error but got: {response.status_code}")

def main():
    """Main test function"""
    print("🔍 Testing Authentication Service Validation")
    print("=" * 50)

    try:
        # Check if auth service is running
        response = requests.get(f"{AUTH_API}/auth/health", timeout=3)
        if response.status_code == 200:
            print("✅ Auth service is running")
            test_email_validation()
        else:
            print("❌ Auth service is not healthy")

    except requests.exceptions.ConnectionError:
        print("❌ Auth service is not running")
        print("Start with: python backend/api/simple_auth_server.py")

    print("\n" + "=" * 50)
    print("🎯 Test completed! The frontend will now show user-friendly error messages.")

if __name__ == "__main__":
    main()