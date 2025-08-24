"""Web API routes for Zorix Agent."""

from fastapi import APIRouter
from agent.web.models import HealthCheck, SystemStatus
from datetime import datetime

# Create simple routers without circular dependencies
chat_router = APIRouter(prefix="/api/v1/chat", tags=["chat"])
files_router = APIRouter(prefix="/api/v1/files", tags=["files"])
projects_router = APIRouter(prefix="/api/v1/projects", tags=["projects"])
search_router = APIRouter(prefix="/api/v1/search", tags=["search"])
tasks_router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])
system_router = APIRouter(prefix="/api/v1/system", tags=["system"])

# Simple health check endpoint
@system_router.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint."""
    return HealthCheck(
        status="healthy",
        timestamp=datetime.now(),
        services={
            "bedrock": "healthy",
            "vector_index": "healthy", 
            "memory": "healthy"
        },
        version="1.0.0"
    )

@system_router.get("/status", response_model=SystemStatus)
async def system_status():
    """System status endpoint."""
    return SystemStatus(
        status="running",
        version="1.0.0",
        uptime_seconds=3600,
        active_tasks=0,
        total_tasks_completed=0,
        memory_usage_mb=512.0,
        workspace_path="./workspace",
        bedrock_status="healthy",
        vector_index_status="healthy",
        memory_stats={}
    )

# Simple placeholder endpoints for other routers
@chat_router.post("/message")
async def chat_message():
    """Chat message endpoint."""
    return {"message": "Chat functionality not yet implemented", "status": "placeholder"}

@tasks_router.post("/execute")
async def execute_task():
    """Task execution endpoint."""
    return {"message": "Task execution not yet implemented", "status": "placeholder"}

@search_router.post("/")
async def search():
    """Search endpoint."""
    return {"message": "Search functionality not yet implemented", "status": "placeholder"}

@files_router.get("/list")
async def list_files():
    """File listing endpoint."""
    return {"message": "File operations not yet implemented", "status": "placeholder"}

@projects_router.get("/")
async def list_projects():
    """Project listing endpoint."""
    return {"message": "Project management not yet implemented", "status": "placeholder"}

__all__ = [
    "chat_router",
    "files_router", 
    "projects_router",
    "search_router",
    "system_router",
    "tasks_router",
]