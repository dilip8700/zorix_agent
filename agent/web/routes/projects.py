"""Project management API routes."""

import logging
from datetime import datetime
from typing import List
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from agent.web.api import get_app_state
from agent.web.models import ProjectInfo

logger = logging.getLogger(__name__)

router = APIRouter()

# Simple in-memory project storage (would be replaced with database)
projects_db = {}


@router.get("/", response_model=List[ProjectInfo])
async def list_projects():
    """List all projects."""
    app_state = get_app_state()
    memory_provider = app_state.get("memory_provider")
    
    if not memory_provider:
        # Return mock data if memory provider not available
        return list(projects_db.values())
    
    try:
        # Get projects from memory provider
        projects = await memory_provider.list_projects()
        
        project_infos = []
        for project in projects:
            project_infos.append(ProjectInfo(
                id=project.id,
                name=project.name,
                description=project.description or "",
                workspace_path=project.workspace_path,
                created_at=project.created_at,
                updated_at=project.updated_at,
                is_current=project.is_current,
                memory_count=len(project.memories) if hasattr(project, 'memories') else 0,
                file_patterns=project.file_patterns or [],
                dependencies=project.dependencies or []
            ))
        
        return project_infos
        
    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")


@router.post("/", response_model=ProjectInfo)
async def create_project(name: str, description: str = "", workspace_path: str = ""):
    """Create a new project."""
    app_state = get_app_state()
    memory_provider = app_state.get("memory_provider")
    settings = app_state.get("settings")
    
    project_id = str(uuid4())
    
    # Use current workspace if not specified
    if not workspace_path and settings:
        workspace_path = settings.workspace_root
    
    project_info = ProjectInfo(
        id=project_id,
        name=name,
        description=description,
        workspace_path=workspace_path,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        is_current=False,
        memory_count=0,
        file_patterns=[],
        dependencies=[]
    )
    
    if memory_provider:
        try:
            # Create project in memory provider
            await memory_provider.create_project(
                project_id=project_id,
                name=name,
                description=description,
                workspace_path=workspace_path
            )
        except Exception as e:
            logger.error(f"Failed to create project in memory: {e}")
            # Continue with in-memory storage
    
    # Store in local cache
    projects_db[project_id] = project_info
    
    return project_info


@router.get("/{project_id}", response_model=ProjectInfo)
async def get_project(project_id: str):
    """Get project details."""
    app_state = get_app_state()
    memory_provider = app_state.get("memory_provider")
    
    if memory_provider:
        try:
            project = await memory_provider.get_project(project_id)
            if project:
                return ProjectInfo(
                    id=project.id,
                    name=project.name,
                    description=project.description or "",
                    workspace_path=project.workspace_path,
                    created_at=project.created_at,
                    updated_at=project.updated_at,
                    is_current=project.is_current,
                    memory_count=len(project.memories) if hasattr(project, 'memories') else 0,
                    file_patterns=project.file_patterns or [],
                    dependencies=project.dependencies or []
                )
        except Exception as e:
            logger.error(f"Failed to get project from memory: {e}")
    
    # Check local cache
    if project_id in projects_db:
        return projects_db[project_id]
    
    raise HTTPException(status_code=404, detail="Project not found")


@router.put("/{project_id}", response_model=ProjectInfo)
async def update_project(project_id: str, name: str = None, description: str = None):
    """Update project details."""
    app_state = get_app_state()
    memory_provider = app_state.get("memory_provider")
    
    # Get existing project
    project = None
    if memory_provider:
        try:
            project = await memory_provider.get_project(project_id)
        except Exception as e:
            logger.error(f"Failed to get project from memory: {e}")
    
    if not project and project_id in projects_db:
        project = projects_db[project_id]
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Update fields
    if name is not None:
        project.name = name
    if description is not None:
        project.description = description
    
    project.updated_at = datetime.now()
    
    # Update in memory provider
    if memory_provider:
        try:
            await memory_provider.update_project(
                project_id=project_id,
                name=project.name,
                description=project.description
            )
        except Exception as e:
            logger.error(f"Failed to update project in memory: {e}")
    
    # Update local cache
    projects_db[project_id] = project
    
    return project


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    """Delete a project."""
    app_state = get_app_state()
    memory_provider = app_state.get("memory_provider")
    
    # Check if project exists
    project_exists = False
    if memory_provider:
        try:
            project = await memory_provider.get_project(project_id)
            project_exists = project is not None
        except Exception as e:
            logger.error(f"Failed to check project in memory: {e}")
    
    if not project_exists and project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Delete from memory provider
    if memory_provider:
        try:
            await memory_provider.delete_project(project_id)
        except Exception as e:
            logger.error(f"Failed to delete project from memory: {e}")
    
    # Delete from local cache
    if project_id in projects_db:
        del projects_db[project_id]
    
    return {"message": f"Project {project_id} deleted successfully"}


@router.post("/{project_id}/activate")
async def activate_project(project_id: str):
    """Set project as current/active."""
    app_state = get_app_state()
    memory_provider = app_state.get("memory_provider")
    
    if memory_provider:
        try:
            await memory_provider.set_current_project(project_id)
        except Exception as e:
            logger.error(f"Failed to activate project in memory: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to activate project: {str(e)}")
    
    # Update local cache
    for pid, project in projects_db.items():
        project.is_current = (pid == project_id)
    
    return {"message": f"Project {project_id} activated"}


@router.get("/{project_id}/memories")
async def get_project_memories(project_id: str, limit: int = 50):
    """Get memories associated with a project."""
    app_state = get_app_state()
    memory_provider = app_state.get("memory_provider")
    
    if not memory_provider:
        raise HTTPException(status_code=500, detail="Memory provider not available")
    
    try:
        memories = await memory_provider.get_project_memories(project_id, limit=limit)
        
        return {
            "project_id": project_id,
            "memories": [
                {
                    "id": memory.id,
                    "content": memory.content,
                    "memory_type": memory.memory_type,
                    "created_at": memory.created_at,
                    "metadata": memory.metadata
                }
                for memory in memories
            ],
            "total": len(memories)
        }
        
    except Exception as e:
        logger.error(f"Failed to get project memories: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get project memories: {str(e)}")


@router.post("/{project_id}/index")
async def index_project(project_id: str):
    """Index project files for search."""
    app_state = get_app_state()
    vector_index = app_state.get("vector_index")
    memory_provider = app_state.get("memory_provider")
    
    if not vector_index:
        raise HTTPException(status_code=500, detail="Vector index not available")
    
    try:
        # Get project details
        project = None
        if memory_provider:
            project = await memory_provider.get_project(project_id)
        
        if not project and project_id in projects_db:
            project = projects_db[project_id]
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Index project workspace
        indexed_files = await vector_index.index_workspace(project.workspace_path)
        
        return {
            "message": f"Project {project_id} indexed successfully",
            "indexed_files": len(indexed_files),
            "files": indexed_files
        }
        
    except Exception as e:
        logger.error(f"Failed to index project: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to index project: {str(e)}")


@router.get("/{project_id}/stats")
async def get_project_stats(project_id: str):
    """Get project statistics."""
    app_state = get_app_state()
    memory_provider = app_state.get("memory_provider")
    
    try:
        stats = {
            "project_id": project_id,
            "memory_count": 0,
            "conversation_count": 0,
            "file_count": 0,
            "last_activity": None
        }
        
        if memory_provider:
            # Get memory stats
            memories = await memory_provider.get_project_memories(project_id)
            stats["memory_count"] = len(memories)
            
            # Get conversation stats
            conversations = await memory_provider.get_project_conversations(project_id)
            stats["conversation_count"] = len(conversations)
            
            if memories:
                stats["last_activity"] = max(memory.created_at for memory in memories)
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get project stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get project stats: {str(e)}")