#!/usr/bin/env python3
"""
Test Runner for AI Social Support Application

This script helps test the system using synthetic data and sample documents.
"""

import json
import requests
import time
from pathlib import Path
import sys

API_BASE_URL = "http://localhost:8000"

def load_sample_data():
    """Load sample application data"""
    data_file = Path(__file__).parent / "sample_applications.json"
    with open(data_file, 'r') as f:
        return json.load(f)

def test_api_connection():
    """Test if the API is accessible"""
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            print("✅ API connection successful")
            return True
        else:
            print(f"❌ API connection failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API connection error: {str(e)}")
        return False

def submit_test_application(applicant_data):
    """Submit a test application"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/applications/submit",
            json=applicant_data
        )

        if response.status_code == 200:
            result = response.json()
            print(f"✅ Application submitted successfully")
            print(f"   Application ID: {result['application_id']}")
            return result['application_id']
        else:
            print(f"❌ Application submission failed: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Application submission error: {str(e)}")
        return None

def check_processing_status(application_id):
    """Check application processing status"""
    try:
        response = requests.get(f"{API_BASE_URL}/applications/{application_id}/status")

        if response.status_code == 200:
            status = response.json()
            print(f"📊 Status: {status.get('status', 'unknown')}")
            if 'progress' in status:
                print(f"   Progress: {status['progress']}%")
            if 'current_stage' in status:
                print(f"   Stage: {status['current_stage']}")
            return status
        else:
            print(f"❌ Status check failed: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Status check error: {str(e)}")
        return None

def test_document_processing():
    """Test document processing endpoint"""
    print("\n🧪 Testing document processing...")

    # Create a simple test document
    test_content = """
    Sample Bank Statement
    Account Holder: John Doe
    Account Number: 1234567890
    Statement Period: January 2024
    Opening Balance: AED 5,000
    Closing Balance: AED 3,200
    Total Credits: AED 8,500
    Total Debits: AED 10,300
    """

    # Create temporary file
    test_file_path = Path("/tmp/test_bank_statement.txt")
    with open(test_file_path, 'w') as f:
        f.write(test_content)

    try:
        with open(test_file_path, 'rb') as f:
            files = {'file': ('test_bank_statement.txt', f, 'text/plain')}
            data = {'document_type': 'bank_statement'}

            response = requests.post(
                f"{API_BASE_URL}/documents/process",
                files=files,
                data=data
            )

            if response.status_code == 200:
                result = response.json()
                print("✅ Document processing successful")
                print(f"   Extracted fields: {len(result.get('extracted_data', {}))}")
                return True
            else:
                print(f"❌ Document processing failed: {response.text}")
                return False

    except Exception as e:
        print(f"❌ Document processing error: {str(e)}")
        return False
    finally:
        # Clean up test file
        if test_file_path.exists():
            test_file_path.unlink()

def test_search_functionality():
    """Test search functionality"""
    print("\n🔍 Testing search functionality...")

    try:
        response = requests.get(
            f"{API_BASE_URL}/search/similar-applications",
            params={'query': 'unemployed family financial support', 'limit': 3}
        )

        if response.status_code == 200:
            result = response.json()
            print("✅ Search functionality working")
            print(f"   Found {len(result.get('results', []))} similar applications")
            return True
        else:
            print(f"❌ Search failed: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Search error: {str(e)}")
        return False

def run_full_application_test(sample_index=0):
    """Run a full application test with sample data"""
    print(f"\n🚀 Running full application test (Sample {sample_index + 1})...")

    sample_data = load_sample_data()
    if sample_index >= len(sample_data):
        print(f"❌ Sample {sample_index + 1} not found")
        return False

    sample = sample_data[sample_index]
    applicant_data = sample['applicant']

    print(f"   Testing with: {applicant_data['first_name']} {applicant_data['last_name']}")

    # Submit application
    application_id = submit_test_application(applicant_data)
    if not application_id:
        return False

    # Check initial status
    print("\n📊 Checking initial status...")
    status = check_processing_status(application_id)

    print(f"\n✅ Test application {application_id} created successfully")
    print("   You can now:")
    print("   1. Open the Streamlit UI (http://localhost:8501)")
    print("   2. Use the existing application ID to upload documents")
    print("   3. Monitor processing in real-time")

    return True

def run_system_health_check():
    """Run comprehensive system health check"""
    print("🏥 Running system health check...\n")

    health_status = {
        "api_connection": False,
        "document_processing": False,
        "search_functionality": False
    }

    # Test API connection
    print("1. Testing API connection...")
    health_status["api_connection"] = test_api_connection()

    # Test document processing
    print("\n2. Testing document processing...")
    health_status["document_processing"] = test_document_processing()

    # Test search functionality
    print("\n3. Testing search functionality...")
    health_status["search_functionality"] = test_search_functionality()

    # Get system stats
    print("\n📈 System statistics:")
    try:
        response = requests.get(f"{API_BASE_URL}/analytics/stats")
        if response.status_code == 200:
            stats = response.json()
            print(f"   Total applications: {stats.get('total_applications', 0)}")
            print(f"   System health: {stats.get('system_health', 'Unknown')}")
        else:
            print("   Stats unavailable")
    except Exception as e:
        print(f"   Stats error: {str(e)}")

    # Summary
    print("\n📋 Health Check Summary:")
    passed = sum(health_status.values())
    total = len(health_status)

    for check, status in health_status.items():
        emoji = "✅" if status else "❌"
        print(f"   {emoji} {check.replace('_', ' ').title()}")

    print(f"\n🎯 Overall: {passed}/{total} checks passed")

    if passed == total:
        print("🎉 All systems operational!")
        return True
    else:
        print("⚠️  Some systems need attention")
        return False

def main():
    """Main test runner"""
    print("🤖 AI Social Support Application - Test Runner")
    print("=" * 50)

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "health":
            run_system_health_check()
        elif command == "app":
            sample_index = int(sys.argv[2]) - 1 if len(sys.argv) > 2 else 0
            run_full_application_test(sample_index)
        elif command == "doc":
            test_document_processing()
        elif command == "search":
            test_search_functionality()
        else:
            print("Unknown command. Available commands:")
            print("  health  - Run system health check")
            print("  app [N] - Run full application test (N = sample number 1-6)")
            print("  doc     - Test document processing")
            print("  search  - Test search functionality")
    else:
        print("Usage: python test_runner.py <command>")
        print("\nCommands:")
        print("  health  - Run system health check")
        print("  app [N] - Run full application test (N = sample number 1-6)")
        print("  doc     - Test document processing")
        print("  search  - Test search functionality")
        print("\nExamples:")
        print("  python test_runner.py health")
        print("  python test_runner.py app 1")
        print("  python test_runner.py doc")

if __name__ == "__main__":
    main()