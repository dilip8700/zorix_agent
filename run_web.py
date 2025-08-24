#!/usr/bin/env python3
"""
Zorix Agent Web Interface Runner

This script starts the FastAPI web server for the Zorix Agent.
"""

import asyncio
import logging
import sys
from pathlib import Path

import uvicorn

# Add the agent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from agent.web.api import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Main entry point for the web application."""
    
    # Import CENTRAL configuration
    try:
        from CENTRAL_CONFIG import SERVER_HOST, SERVER_PORT, BASE_URL, API_DOCS_URL, CHAT_URL
        host = SERVER_HOST
        port = SERVER_PORT
    except ImportError:
        # Fallback to agent config
        from agent.config import get_settings
        settings = get_settings()
        host = settings.host
        port = settings.app_port
    
    # Create FastAPI app
    app = create_app()
    
    logger.info(f"Starting Zorix Agent Web Interface on http://{host}:{port}")
    logger.info(f"API Documentation available at http://{host}:{port}/docs")
    logger.info(f"Web Interface available at http://{host}:{port}/static/index.html")
    
    # Run the server
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        reload=False  # Set to True for development
    )


if __name__ == "__main__":
    main()