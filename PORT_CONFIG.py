#!/usr/bin/env python3
"""
🔧 CENTRALIZED PORT CONFIGURATION FOR ZORIX AGENT
==================================================

🎯 CHANGE THE PORT HERE TO UPDATE IT EVERYWHERE!

This file centralizes the port configuration for the entire Zorix Agent system.
When you change the port here, it will be used by:
- Web server (run_web.py)
- Simple server (simple_start.py) 
- AI chat server (start_with_ai.py)
- CLI tool (zorix_cli.py)
- All API endpoints
- Documentation URLs

📝 HOW TO CHANGE THE PORT:
1. Change the ZORIX_PORT value below
2. Restart any running servers
3. That's it! Everything will use the new port.

🚨 IMPORTANT: Make sure the port is not already in use by another application.
"""

# 🎯 CHANGE THIS VALUE TO CHANGE THE PORT EVERYWHERE
ZORIX_PORT = 8001

# 🌐 HOST CONFIGURATION (usually don't need to change this)
ZORIX_HOST = "127.0.0.1"

# 📚 DERIVED URLS (automatically generated from above)
ZORIX_BASE_URL = f"http://{ZORIX_HOST}:{ZORIX_PORT}"
ZORIX_API_DOCS_URL = f"{ZORIX_BASE_URL}/docs"
ZORIX_HEALTH_URL = f"{ZORIX_BASE_URL}/health"
ZORIX_CHAT_URL = f"{ZORIX_BASE_URL}/static/index.html"

def get_port():
    """Get the configured port."""
    return ZORIX_PORT

def get_host():
    """Get the configured host."""
    return ZORIX_HOST

def get_base_url():
    """Get the base URL."""
    return ZORIX_BASE_URL

def get_api_docs_url():
    """Get the API documentation URL."""
    return ZORIX_API_DOCS_URL

def get_health_url():
    """Get the health check URL."""
    return ZORIX_HEALTH_URL

def get_chat_url():
    """Get the chat interface URL."""
    return ZORIX_CHAT_URL

def print_urls():
    """Print all access URLs."""
    print("🌐 Zorix Agent Access URLs:")
    print(f"   • Main Interface: {ZORIX_BASE_URL}")
    print(f"   • Chat Interface: {ZORIX_CHAT_URL}")
    print(f"   • API Documentation: {ZORIX_API_DOCS_URL}")
    print(f"   • Health Check: {ZORIX_HEALTH_URL}")

if __name__ == "__main__":
    print("🔧 Zorix Agent Port Configuration")
    print("=" * 40)
    print(f"Port: {ZORIX_PORT}")
    print(f"Host: {ZORIX_HOST}")
    print()
    print_urls()