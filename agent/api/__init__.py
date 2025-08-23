"""FastAPI application and routing for Zorix Agent."""

from .app import create_app
from .middleware import setup_middleware
from .routes import setup_routes

__all__ = [
    "create_app",
    "setup_middleware", 
    "setup_routes",
]