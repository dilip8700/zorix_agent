#!/usr/bin/env python3
"""
🚀 ZORIX AGENT UNIFIED STARTER
==============================

This is the main startup script for Zorix Agent.
It uses centralized port configuration from PORT_CONFIG.py

🎯 To change the port: Edit PORT_CONFIG.py
🌐 Default port: 8000 (configurable)

Usage:
    python start_zorix.py          # Start full agent
    python start_zorix.py --simple # Start simple version
    python start_zorix.py --help   # Show help
"""

import sys
import argparse
from pathlib import Path

# Add the agent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

def start_full_agent():
    """Start the full Zorix Agent with all features."""
    try:
        from CENTRAL_CONFIG import SERVER_HOST, SERVER_PORT, print_current_config
        from agent.web.api import create_app
        import uvicorn
        import logging
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        logger = logging.getLogger(__name__)
        
        # Get centralized configuration
        host = SERVER_HOST
        port = SERVER_PORT
        
        # Create FastAPI app
        app = create_app()
        
        print("🤖 Starting Zorix Agent (Full Version)")
        print("=" * 50)
        print_current_config()
        print()
        print("🛑 Press Ctrl+C to stop")
        print()
        
        # Start the server
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            access_log=True,
            reload=False
        )
        
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("💡 Try: pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"❌ Error starting full agent: {e}")
        return False

def start_simple_agent():
    """Start a simple version of Zorix Agent."""
    try:
        from CENTRAL_CONFIG import SERVER_HOST, SERVER_PORT, print_current_config
        from fastapi import FastAPI
        from datetime import datetime
        import uvicorn
        
        # Get centralized configuration
        host = SERVER_HOST
        port = SERVER_PORT
        
        app = FastAPI(title="Zorix Agent (Simple)", version="1.0.0")
        
        @app.get("/")
        async def root():
            return {
                "message": "Zorix Agent is running! (Simple Mode)",
                "version": "1.0.0", 
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "mode": "simple",
                "port": port
            }
        
        @app.get("/health")
        async def health():
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "mode": "simple"
            }
            
        @app.get("/status")
        async def status():
            return {
                "status": "running",
                "version": "1.0.0",
                "message": "Zorix Agent (Simple Mode) is operational",
                "port": port,
                "mode": "simple"
            }
        
        print("🤖 Starting Zorix Agent (Simple Version)")
        print("=" * 50)
        print_current_config()
        print()
        print("ℹ️  Simple mode - limited features")
        print("🛑 Press Ctrl+C to stop")
        print()
        
        uvicorn.run(app, host=host, port=port, log_level="info")
        
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("💡 Installing basic dependencies...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn[standard]"])
        print("✅ Dependencies installed. Please run again.")
        return False
    except Exception as e:
        print(f"❌ Error starting simple agent: {e}")
        return False

def show_port_info():
    """Show current port configuration."""
    try:
        from CENTRAL_CONFIG import print_current_config
        print_current_config()
    except ImportError:
        print("❌ CENTRAL_CONFIG.py not found")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Zorix Agent - AI-powered development assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python start_zorix.py              # Start full agent
  python start_zorix.py --simple     # Start simple version  
  python start_zorix.py --port-info  # Show port configuration
  
To change port: Edit PORT_CONFIG.py
        """
    )
    
    parser.add_argument(
        "--simple", 
        action="store_true", 
        help="Start simple version with basic features"
    )
    
    parser.add_argument(
        "--port-info", 
        action="store_true", 
        help="Show current port configuration"
    )
    
    args = parser.parse_args()
    
    if args.port_info:
        show_port_info()
        return
    
    if args.simple:
        success = start_simple_agent()
    else:
        success = start_full_agent()
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()