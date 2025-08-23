#!/usr/bin/env python3
"""Main entry point for Zorix Agent."""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from agent.config import validate_startup_config


def main():
    """Main entry point."""
    try:
        # Validate configuration
        validate_startup_config()
        
        # Import and run the FastAPI app
        import uvicorn
        from agent.api import app
        
        # Get configuration
        from agent.config import get_settings
        settings = get_settings()
        
        print(f"🚀 Starting Zorix Agent on {settings.host}:{settings.app_port}")
        
        # Run the server
        uvicorn.run(
            "agent.api:app",
            host=settings.host,
            port=settings.app_port,
            reload=True,
            log_level=settings.log_level.lower()
        )
        
    except Exception as e:
        print(f"❌ Failed to start Zorix Agent: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()