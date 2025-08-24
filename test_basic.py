#!/usr/bin/env python3
"""Basic test to verify the foundation is working."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_config():
    """Test configuration loading."""
    from agent.config import get_settings, validate_startup_config
    
    print("Testing configuration...")
    settings = get_settings()
    # Updated to match CENTRAL_CONFIG.py values
    assert settings.app_port == 8002
    assert settings.bedrock_region == "us-east-1"
    
    validate_startup_config()
    print("✅ Configuration test passed")


def test_api_creation():
    """Test FastAPI app creation."""
    from agent.api import app
    
    print("Testing API creation...")
    assert app is not None
    assert app.title == "Zorix Agent"
    print("✅ API creation test passed")


def test_health_endpoint():
    """Test health endpoint."""
    from fastapi.testclient import TestClient
    from agent.api import app
    
    print("Testing health endpoint...")
    client = TestClient(app)
    response = client.get("/healthz")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "zorix-agent"
    print("✅ Health endpoint test passed")


if __name__ == "__main__":
    try:
        test_config()
        test_api_creation()
        test_health_endpoint()
        print("\n🎉 All foundation tests passed!")
        print("✅ Task 1: Project Foundation and Configuration - COMPLETE")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)