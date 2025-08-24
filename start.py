#!/usr/bin/env python3
"""
Quick Start Script for Zorix Agent

This script provides the fastest way to get Zorix Agent running.
"""

import subprocess
import sys
import time
import webbrowser
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import fastapi
        import uvicorn
        print("✅ FastAPI and Uvicorn are installed")
        return True
    except ImportError:
        print("❌ Missing dependencies. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn[standard]"])
            print("✅ Dependencies installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install dependencies")
            return False

def find_available_port():
    """Find an available port to run the server."""
    import socket
    
    for port in range(8000, 8010):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    return 8000

def main():
    """Main startup function."""
    print("🚀 Starting Zorix Agent...")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        print("❌ Cannot start without required dependencies")
        return
    
    # Find available port
    port = find_available_port()
    
    # Create simple server script
    server_script = f'''
import uvicorn
from fastapi import FastAPI
from datetime import datetime

app = FastAPI(title="Zorix Agent", version="1.0.0")

@app.get("/")
async def root():
    return {{
        "message": "Zorix Agent is running!",
        "version": "1.0.0",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "endpoints": [
            "GET /health - Health check",
            "GET /docs - API documentation", 
            "GET /status - System status"
        ]
    }}

@app.get("/health")
async def health():
    return {{
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "message": "System is running normally"
    }}

@app.get("/status")
async def status():
    return {{
        "status": "running",
        "version": "1.0.0",
        "message": "Zorix Agent is operational",
        "note": "This is a minimal version. Full features require AWS Bedrock setup."
    }}

if __name__ == "__main__":
    print("🌐 Server starting on http://127.0.0.1:{port}")
    print("📚 API docs: http://127.0.0.1:{port}/docs")
    print("❤️  Health: http://127.0.0.1:{port}/health")
    print("📊 Status: http://127.0.0.1:{port}/status")
    print("\\n🛑 Press Ctrl+C to stop")
    
    uvicorn.run(app, host="127.0.0.1", port={port}, log_level="info")
'''
    
    # Write and run the server
    server_file = Path("temp_server.py")
    server_file.write_text(server_script, encoding='utf-8')
    
    try:
        print(f"🌐 Starting server on port {port}...")
        print(f"📚 API Documentation: http://127.0.0.1:{port}/docs")
        print(f"❤️  Health Check: http://127.0.0.1:{port}/health")
        print(f"📊 System Status: http://127.0.0.1:{port}/status")
        print("\\n🛑 Press Ctrl+C to stop the server")
        print("=" * 50)
        
        # Try to open browser
        try:
            time.sleep(1)
            webbrowser.open(f"http://127.0.0.1:{port}")
        except:
            pass
        
        # Run the server
        subprocess.run([sys.executable, "temp_server.py"])
        
    except KeyboardInterrupt:
        print("\\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
    finally:
        # Cleanup
        if server_file.exists():
            server_file.unlink()

if __name__ == "__main__":
    main()