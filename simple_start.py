#!/usr/bin/env python3
"""
Ultra Simple Zorix Agent Starter
"""

def main():
    try:
        import uvicorn
        from fastapi import FastAPI
        from datetime import datetime
        
        # Import CENTRAL configuration
        try:
            from CENTRAL_CONFIG import SERVER_HOST, SERVER_PORT
            host = SERVER_HOST
            port = SERVER_PORT
        except ImportError:
            # Fallback to agent config
            try:
                from agent.config import get_settings
                settings = get_settings()
                host = settings.host
                port = settings.app_port
            except ImportError:
                # Final fallback
                host = "127.0.0.1"
                port = 8001
        
        app = FastAPI(title="Zorix Agent", version="1.0.0")
        
        @app.get("/")
        async def root():
            return {
                "message": "Zorix Agent is running!",
                "version": "1.0.0", 
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "port": port
            }
        
        @app.get("/health")
        async def health():
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat()
            }
            
        @app.get("/status")
        async def status():
            return {
                "status": "running",
                "version": "1.0.0",
                "message": "Basic Zorix Agent is operational",
                "port": port
            }
        
        print(f"Starting Zorix Agent on http://{host}:{port}")
        print(f"API docs: http://{host}:{port}/docs")
        print(f"Health: http://{host}:{port}/health")
        print("Press Ctrl+C to stop")
        
        uvicorn.run(app, host=host, port=port, log_level="info")
        
    except ImportError:
        print("Installing required packages...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn[standard]"])
        print("Please run the script again")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()