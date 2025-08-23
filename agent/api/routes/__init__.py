"""API routes for Zorix Agent."""

from fastapi import FastAPI

from .agent import router as agent_router
from .chat import router as chat_router
from .git import router as git_router
from .health import router as health_router
from .index import router as index_router
from .search import router as search_router


def setup_routes(app: FastAPI) -> None:
    """Setup all API routes.
    
    Args:
        app: FastAPI application instance
    """
    # Include routers with prefixes
    app.include_router(health_router, prefix="/health", tags=["Health"])
    app.include_router(agent_router, prefix="/agent", tags=["Agent"])
    app.include_router(chat_router, prefix="/chat", tags=["Chat"])
    app.include_router(search_router, prefix="/search", tags=["Search"])
    app.include_router(git_router, prefix="/git", tags=["Git"])
    app.include_router(index_router, prefix="/index", tags=["Index"])


__all__ = [
    "setup_routes",
    "agent_router",
    "chat_router", 
    "git_router",
    "health_router",
    "index_router",
    "search_router",
]