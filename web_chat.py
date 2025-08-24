#!/usr/bin/env python3
"""
Web-based Chat with Zorix Agent

This script provides a simple way to chat via the web API.
"""

import requests
import json
import time

def chat_via_api(message, base_url="http://127.0.0.1:8001"):
    """Send a chat message via the web API."""
    try:
        response = requests.post(
            f"{base_url}/api/v1/chat/message",
            json={
                "message": message,
                "session_id": "web-chat-session"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return True, result.get('message', 'No response')
        else:
            return False, f"API Error: {response.status_code} - {response.text}"
            
    except requests.exceptions.ConnectionError:
        return False, "Connection failed - is the server running?"
    except Exception as e:
        return False, f"Error: {e}"

def interactive_web_chat():
    """Interactive chat via web API."""
    print("🌐 Zorix Agent Web Chat")
    print("=" * 40)
    print("Make sure your server is running!")
    print("Type 'quit' to exit")
    print()
    
    # Test connection first
    print("🔍 Testing server connection...")
    success, response = chat_via_api("Hello, are you working?")
    
    if not success:
        print(f"❌ {response}")
        print("💡 Start your server with: python simple_start.py")
        return
    
    print("✅ Server connected!")
    print()
    
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("👋 Goodbye!")
            break
        
        if not user_input:
            continue
        
        print("🤖 AI: ", end="", flush=True)
        
        success, response = chat_via_api(user_input)
        
        if success:
            print(response)
        else:
            print(f"Error: {response}")
        
        print()

if __name__ == "__main__":
    interactive_web_chat()