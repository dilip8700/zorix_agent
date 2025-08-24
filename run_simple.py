#!/usr/bin/env python3
"""
Simple Zorix Agent Web Server

A minimal working version without complex dependencies.
"""

import logging
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def create_simple_app():
    """Create a simple FastAPI app."""
    
    app = FastAPI(
        title="Zorix Agent",
        description="AI-powered development agent",
        version="1.0.0"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "message": "Zorix Agent is running",
            "version": "1.0.0",
            "status": "healthy",
            "timestamp": datetime.now().isoformat()
        }
    
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "api": "healthy",
                "web": "healthy"
            },
            "version": "1.0.0"
        }
    
    @app.get("/api/v1/system/health")
    async def system_health():
        """System health endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "bedrock": "not_configured",
                "vector_index": "not_configured", 
                "memory": "not_configured"
            },
            "version": "1.0.0"
        }
    
    @app.get("/api/v1/system/status")
    async def system_status():
        """System status endpoint."""
        return {
            "status": "running",
            "version": "1.0.0",
            "uptime_seconds": 0,
            "active_tasks": 0,
            "total_tasks_completed": 0,
            "memory_usage_mb": 0,
            "workspace_path": "./workspace",
            "bedrock_status": "not_configured",
            "vector_index_status": "not_configured",
            "memory_stats": {}
        }
    
    @app.post("/api/v1/chat/message")
    async def chat_message():
        """Chat message endpoint."""
        return {
            "message": "Chat functionality requires AWS Bedrock configuration",
            "status": "not_configured",
            "timestamp": datetime.now().isoformat()
        }
    
    @app.post("/api/v1/tasks/execute")
    async def execute_task():
        """Task execution endpoint."""
        return {
            "message": "Task execution requires full system setup",
            "status": "not_configured",
            "timestamp": datetime.now().isoformat()
        }
    
    return app


def main():
    """Main entry point for the simple web application."""
    
    app = create_simple_app()
    
    # Configuration
    host = "127.0.0.1"
    port = 8001
    
    logger.info(f"Starting Simple Zorix Agent on http://{host}:{port}")
    logger.info(f"API Documentation available at http://127.0.0.1:{port}/docs")
    logger.info(f"Health check available at http://127.0.0.1:{port}/health")
    
    # Run the server
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        reload=False
    )


if __name__ == "__main__":
    main()