"""Health check and system status endpoints."""

import logging
import platform
import psutil
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.config import get_settings
from agent.llm.bedrock_client import BedrockClient

logger = logging.getLogger(__name__)

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: str
    version: str
    uptime_seconds: float


class SystemStatusResponse(BaseModel):
    """System status response model."""
    status: str
    timestamp: str
    system: Dict[str, Any]
    resources: Dict[str, Any]
    services: Dict[str, Any]
    workspace: Dict[str, Any]


# Track application start time
_start_time = datetime.now(timezone.utc)


@router.get("/", response_model=HealthResponse)
async def health_check():
    """Basic health check endpoint.
    
    Returns:
        Health status information
    """
    try:
        current_time = datetime.now(timezone.utc)
        uptime = (current_time - _start_time).total_seconds()
        
        return HealthResponse(
            status="healthy",
            timestamp=current_time.isoformat(),
            version="1.0.0",
            uptime_seconds=uptime
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")


@router.get("/status", response_model=SystemStatusResponse)
async def system_status():
    """Detailed system status endpoint.
    
    Returns:
        Comprehensive system status information
    """
    try:
        settings = get_settings()
        current_time = datetime.now(timezone.utc)
        uptime = (current_time - _start_time).total_seconds()
        
        # System information
        system_info = {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
            "uptime_seconds": uptime,
        }
        
        # Resource usage
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        resources = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent,
                "used": memory.used,
            },
            "disk": {
                "total": disk.total,
                "free": disk.free,
                "used": disk.used,
                "percent": (disk.used / disk.total) * 100,
            },
        }
        
        # Service status
        services = {
            "bedrock": await _check_bedrock_service(),
            "workspace": _check_workspace_access(settings.workspace_root),
            "memory_db": _check_memory_db_access(settings.memory_db_path),
        }
        
        # Workspace information
        workspace_info = {
            "root": settings.workspace_root,
            "exists": _check_workspace_access(settings.workspace_root),
            "memory_db_path": settings.memory_db_path,
            "vector_index_path": settings.vector_index_path,
        }
        
        return SystemStatusResponse(
            status="healthy" if all(services.values()) else "degraded",
            timestamp=current_time.isoformat(),
            system=system_info,
            resources=resources,
            services=services,
            workspace=workspace_info
        )
        
    except Exception as e:
        logger.error(f"System status check failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system status")


@router.get("/ready")
async def readiness_check():
    """Readiness check for Kubernetes/container orchestration.
    
    Returns:
        Simple ready/not ready status
    """
    try:
        settings = get_settings()
        
        # Check critical dependencies
        checks = {
            "workspace": _check_workspace_access(settings.workspace_root),
            "bedrock": await _check_bedrock_service(),
        }
        
        if all(checks.values()):
            return {"status": "ready", "checks": checks}
        else:
            raise HTTPException(
                status_code=503,
                detail={"status": "not ready", "checks": checks}
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")


@router.get("/live")
async def liveness_check():
    """Liveness check for Kubernetes/container orchestration.
    
    Returns:
        Simple alive/dead status
    """
    try:
        # Basic liveness check - if we can respond, we're alive
        return {
            "status": "alive",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Liveness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not alive")


async def _check_bedrock_service() -> bool:
    """Check if Bedrock service is accessible.
    
    Returns:
        True if Bedrock is accessible
    """
    try:
        bedrock = BedrockClient()
        health_result = await bedrock.health_check()
        return health_result.get("status") == "healthy"
    except Exception as e:
        logger.warning(f"Bedrock health check failed: {e}")
        return False


def _check_workspace_access(workspace_path: str) -> bool:
    """Check if workspace is accessible.
    
    Args:
        workspace_path: Path to workspace
        
    Returns:
        True if workspace is accessible
    """
    try:
        from pathlib import Path
        workspace = Path(workspace_path)
        return workspace.exists() and workspace.is_dir()
    except Exception as e:
        logger.warning(f"Workspace access check failed: {e}")
        return False


def _check_memory_db_access(memory_db_path: str) -> bool:
    """Check if memory database path is accessible.
    
    Args:
        memory_db_path: Path to memory database
        
    Returns:
        True if memory DB path is accessible
    """
    try:
        from pathlib import Path
        db_path = Path(memory_db_path)
        # Create directory if it doesn't exist
        db_path.mkdir(parents=True, exist_ok=True)
        return db_path.exists() and db_path.is_dir()
    except Exception as e:
        logger.warning(f"Memory DB access check failed: {e}")
        return False