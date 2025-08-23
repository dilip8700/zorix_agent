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
    
    # Create FastAPI app
    app = create_app()
    
    # Configuration
    host = "127.0.0.1"
    port = 8000
    
    logger.info(f"Starting Zorix Agent Web Interface on http://{host}:{port}")
    logger.info("API Documentation available at http://127.0.0.1:8000/docs")
    logger.info("Web Interface available at http://127.0.0.1:8000/static/index.html")
    
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