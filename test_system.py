#!/usr/bin/env python3
"""
Test Zorix Agent System
"""

import requests
import json
import time

def test_endpoint(url, method="GET", data=None, description=""):
    """Test an API endpoint."""
    try:
        print(f"🧪 Testing: {description}")
        print(f"   URL: {url}")
        
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Success: {response.status_code}")
            if isinstance(result, dict) and 'message' in result:
                print(f"   📝 Message: {result['message']}")
            elif isinstance(result, dict) and 'status' in result:
                print(f"   📊 Status: {result['status']}")
            return True
        else:
            print(f"   ❌ Failed: {response.status_code}")
            print(f"   📝 Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Connection failed - is the server running?")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    finally:
        print()

def main():
    """Test the Zorix Agent system."""
    
    print("🚀 Testing Zorix Agent System")
    print("=" * 50)
    
    base_url = "http://127.0.0.1:8001"
    
    # Test basic endpoints
    tests = [
        (f"{base_url}/", "GET", None, "Root endpoint"),
        (f"{base_url}/health", "GET", None, "Health check"),
        (f"{base_url}/status", "GET", None, "System status"),
        (f"{base_url}/api/v1/system/health", "GET", None, "API health check"),
        (f"{base_url}/api/v1/system/status", "GET", None, "API system status"),
    ]
    
    # Run basic tests
    passed = 0
    total = len(tests)
    
    for url, method, data, description in tests:
        if test_endpoint(url, method, data, description):
            passed += 1
    
    print("📊 Basic Test Results:")
    print(f"   ✅ Passed: {passed}/{total}")
    print(f"   📈 Success Rate: {(passed/total)*100:.1f}%")
    print()
    
    # Test advanced endpoints (these might not work without AWS)
    print("🤖 Testing AI Features (may require AWS):")
    print("-" * 40)
    
    advanced_tests = [
        (f"{base_url}/api/v1/chat/message", "POST", 
         {"message": "Hello, this is a test"}, 
         "Chat message"),
        (f"{base_url}/api/v1/tasks/execute", "POST", 
         {"instruction": "Create a hello world function", "dry_run": True}, 
         "Task execution"),
    ]
    
    ai_passed = 0
    for url, method, data, description in advanced_tests:
        if test_endpoint(url, method, data, description):
            ai_passed += 1
    
    print("📊 AI Features Test Results:")
    print(f"   ✅ Passed: {ai_passed}/{len(advanced_tests)}")
    if ai_passed == 0:
        print("   💡 AI features require AWS Bedrock configuration")
    print()
    
    # Summary
    print("🎯 Summary:")
    if passed == total:
        print("   ✅ Basic system is working perfectly!")
    else:
        print("   ⚠️  Some basic features need attention")
    
    if ai_passed > 0:
        print("   🤖 AI features are working!")
    else:
        print("   🔧 AI features need AWS configuration")
    
    print()
    print("🌐 Access your system at:")
    print(f"   • Main: {base_url}/")
    print(f"   • Docs: {base_url}/docs")
    print(f"   • Health: {base_url}/health")

if __name__ == "__main__":
    main()