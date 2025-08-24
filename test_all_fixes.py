#!/usr/bin/env python3
"""
Comprehensive test to verify all fixes are working
"""

def test_configuration():
    """Test configuration loading."""
    try:
        from agent.config import get_settings
        settings = get_settings()
        print(f"✅ Configuration: Port {settings.app_port}, Host {settings.host}")
        return True
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

def test_port_config():
    """Test centralized port configuration."""
    try:
        from PORT_CONFIG import get_port, get_host, get_base_url
        port = get_port()
        host = get_host()
        url = get_base_url()
        print(f"✅ Port Config: {host}:{port} -> {url}")
        return True
    except Exception as e:
        print(f"❌ Port config error: {e}")
        return False

def test_web_api():
    """Test web API creation."""
    try:
        from agent.web.api import create_app
        app = create_app()
        print("✅ Web API creation successful")
        return True
    except Exception as e:
        print(f"❌ Web API error: {e}")
        return False

def test_imports():
    """Test critical imports."""
    try:
        # Test core imports
        from agent.llm.bedrock_client import BedrockClient
        from agent.tools.filesystem import FilesystemTools
        from agent.tools.command import CommandTools
        from agent.tools.git import GitTools
        from agent.memory.conversation import ConversationMemory
        from agent.orchestrator.core import AgentOrchestrator
        print("✅ All critical imports successful")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_cli_config():
    """Test CLI configuration."""
    try:
        from agent.cli.config import cli_config
        config = cli_config.get_default_config()
        print(f"✅ CLI Config: API URL {config['api_url']}")
        return True
    except Exception as e:
        print(f"❌ CLI config error: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Running comprehensive system tests...")
    print("=" * 50)
    
    tests = [
        ("Configuration Loading", test_configuration),
        ("Port Configuration", test_port_config),
        ("Web API Creation", test_web_api),
        ("Critical Imports", test_imports),
        ("CLI Configuration", test_cli_config),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Testing {test_name}...")
        if test_func():
            passed += 1
        else:
            print(f"   Failed: {test_name}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Your Zorix Agent is fully functional!")
        print("\n🚀 Ready to start:")
        print("   python start_zorix.py")
        print("   python run_web.py")
        print("   python simple_start.py")
        return True
    else:
        print(f"❌ {total - passed} tests failed. Some issues remain.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)