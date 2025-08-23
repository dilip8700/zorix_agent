"""Main FastAPI application factory."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent.api.middleware import setup_middleware
from agent.api.routes import setup_routes
from agent.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    logger.info("Starting Zorix Agent API")
    
    # Startup
    settings = get_settings()
    logger.info(f"API starting on workspace: {settings.workspace_root}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Zorix Agent API")


def create_app() -> FastAPI:
    """Create and configure FastAPI application.
    
    Returns:
        Configured FastAPI application
    """
    settings = get_settings()
    
    # Create FastAPI app
    app = FastAPI(
        title="Zorix Agent API",
        description="AI-powered development agent with code analysis and task execution",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    
    # Setup CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Setup custom middleware
    setup_middleware(app)
    
    # Setup routes
    setup_routes(app)
    
    logger.info("FastAPI application created successfully")
    return app


# Create the app instance
app = create_app()