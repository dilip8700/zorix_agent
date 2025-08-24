#!/usr/bin/env python3
"""
Start Zorix Agent with AI Chat Functionality

This script starts the full system with AI capabilities.
"""

import subprocess
import sys
import os
import time
from pathlib import Path

def install_dependencies():
    """Install required dependencies."""
    print("📦 Installing dependencies...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "fastapi", "uvicorn[standard]", "boto3", "python-dotenv"
        ])
        print("✅ Dependencies installed")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        return False

def test_aws_credentials():
    """Test AWS credentials."""
    print("🔍 Testing AWS credentials...")
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        import boto3
        client = boto3.client('sts', region_name='us-east-1')
        identity = client.get_caller_identity()
        print(f"✅ AWS credentials working: {identity.get('Arn', 'Unknown')}")
        return True
    except Exception as e:
        print(f"❌ AWS credentials issue: {e}")
        return False

def create_full_server():
    """Create a full server with AI chat."""
    server_code = '''
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from datetime import datetime
import boto3
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="Zorix Agent with AI", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Bedrock client
try:
    bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')
    AI_AVAILABLE = True
except Exception as e:
    print(f"Warning: AWS Bedrock not available: {e}")
    AI_AVAILABLE = False

@app.get("/")
async def root():
    return {
        "message": "Zorix Agent with AI is running!",
        "version": "1.0.0",
        "ai_available": AI_AVAILABLE,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "ai_available": AI_AVAILABLE,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/chat")
async def chat_interface():
    """Serve the chat interface."""
    return FileResponse("chat_interface.html")

@app.post("/api/v1/chat/message")
async def chat_message(request: dict):
    """Chat with AI."""
    if not AI_AVAILABLE:
        return {
            "message": "AI chat requires AWS Bedrock configuration. Please check your credentials.",
            "status": "not_configured",
            "timestamp": datetime.now().isoformat()
        }
    
    try:
        user_message = request.get("message", "")
        if not user_message:
            raise HTTPException(status_code=400, detail="Message is required")
        
        # Call Bedrock
        response = bedrock_client.invoke_model(
            modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "messages": [
                    {
                        "role": "user",
                        "content": f"You are Zorix Agent, an AI coding assistant. Please help with: {user_message}"
                    }
                ]
            })
        )
        
        result = json.loads(response['body'].read())
        ai_response = result['content'][0]['text']
        
        return {
            "message": ai_response,
            "session_id": request.get("session_id", "default"),
            "timestamp": datetime.now().isoformat(),
            "model": "claude-3-5-sonnet"
        }
        
    except Exception as e:
        return {
            "message": f"AI Error: {str(e)}. Please check your AWS Bedrock configuration.",
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }

@app.post("/api/v1/tasks/execute")
async def execute_task(request: dict):
    """Execute a task."""
    return {
        "message": "Task execution is available with full system setup",
        "status": "basic_mode",
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    # Import centralized configuration
    try:
        from agent.config import get_settings
        settings = get_settings()
        host = settings.host
        port = settings.app_port
    except ImportError:
        host = "127.0.0.1"
        port = 8000
    
    print("🚀 Starting Zorix Agent with AI Chat...")
    print(f"🌐 Chat interface: http://{host}:{port}/chat")
    print(f"📚 API docs: http://{host}:{port}/docs")
    print(f"❤️ Health: http://{host}:{port}/health")
    print("\\n🛑 Press Ctrl+C to stop")
    
    uvicorn.run(app, host=host, port=port, log_level="info")
'''
    
    with open("full_server.py", "w", encoding="utf-8") as f:
        f.write(server_code)

def main():
    """Main function."""
    print("🤖 Starting Zorix Agent with AI Chat")
    print("=" * 50)
    
    # Install dependencies
    if not install_dependencies():
        return
    
    # Test AWS
    aws_working = test_aws_credentials()
    
    # Create and run server
    print("🚀 Creating full server...")
    create_full_server()
    
    # Import centralized configuration
    try:
        from agent.config import get_settings
        settings = get_settings()
        host = settings.host
        port = settings.app_port
    except ImportError:
        host = "127.0.0.1"
        port = 8000
    
    print(f"🌐 Starting server on http://{host}:{port}")
    if aws_working:
        print("✅ AI chat will be available!")
    else:
        print("⚠️ AI chat requires AWS Bedrock setup")
    
    print("🎯 Access points:")
    print(f"   • Chat Interface: http://{host}:{port}/chat")
    print(f"   • API Docs: http://{host}:{port}/docs")
    print(f"   • Health: http://{host}:{port}/health")
    print()
    
    try:
        subprocess.run([sys.executable, "full_server.py"])
    except KeyboardInterrupt:
        print("\\n🛑 Server stopped")
    finally:
        # Cleanup
        if os.path.exists("full_server.py"):
            os.remove("full_server.py")

if __name__ == "__main__":
    main()