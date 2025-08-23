"""File management API routes."""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from agent.security.path_utils import is_safe_path
from agent.web.api import get_app_state
from agent.web.models import DirectoryListing, FileContent, FileInfo

logger = logging.getLogger(__name__)

router = APIRouter()


def get_workspace_root() -> Path:
    """Get workspace root path."""
    app_state = get_app_state()
    settings = app_state.get("settings")
    if not settings:
        raise HTTPException(status_code=500, detail="Settings not available")
    return Path(settings.workspace_root)


def validate_path(file_path: str) -> Path:
    """Validate and resolve file path."""
    workspace_root = get_workspace_root()
    
    if not is_safe_path(file_path, str(workspace_root)):
        raise HTTPException(status_code=400, detail="Invalid or unsafe path")
    
    # Convert to absolute path within workspace
    if os.path.isabs(file_path):
        resolved_path = Path(file_path)
    else:
        resolved_path = workspace_root / file_path
    
    # Ensure path is within workspace
    try:
        resolved_path.resolve().relative_to(workspace_root.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Path outside workspace")
    
    return resolved_path


@router.get("/list", response_model=DirectoryListing)
async def list_directory(path: str = ""):
    """List directory contents."""
    try:
        dir_path = validate_path(path) if path else get_workspace_root()
        
        if not dir_path.exists():
            raise HTTPException(status_code=404, detail="Directory not found")
        
        if not dir_path.is_dir():
            raise HTTPException(status_code=400, detail="Path is not a directory")
        
        files = []
        directories = []
        
        for item in dir_path.iterdir():
            try:
                stat = item.stat()
                file_info = FileInfo(
                    path=str(item.relative_to(get_workspace_root())),
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime),
                    is_directory=item.is_dir(),
                    permissions=oct(stat.st_mode)[-3:]
                )
                
                if item.is_dir():
                    directories.append(file_info)
                else:
                    files.append(file_info)
                    
            except (OSError, PermissionError) as e:
                logger.warning(f"Could not access {item}: {e}")
                continue
        
        # Sort by name
        files.sort(key=lambda x: x.path.lower())
        directories.sort(key=lambda x: x.path.lower())
        
        return DirectoryListing(
            path=str(dir_path.relative_to(get_workspace_root())),
            files=files,
            directories=directories,
            total_files=len(files),
            total_directories=len(directories)
        )
        
    except Exception as e:
        logger.error(f"Failed to list directory: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list directory: {str(e)}")


@router.get("/content", response_model=FileContent)
async def get_file_content(path: str, encoding: str = "utf-8"):
    """Get file content."""
    try:
        file_path = validate_path(path)
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")
        
        # Check file size (limit to 10MB for API)
        stat = file_path.stat()
        if stat.st_size > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large for API access")
        
        try:
            content = file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            # Try with different encodings
            for alt_encoding in ['latin-1', 'cp1252', 'utf-16']:
                try:
                    content = file_path.read_text(encoding=alt_encoding)
                    encoding = alt_encoding
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise HTTPException(status_code=400, detail="Could not decode file content")
        
        return FileContent(
            path=str(file_path.relative_to(get_workspace_root())),
            content=content,
            encoding=encoding,
            size=stat.st_size,
            modified=datetime.fromtimestamp(stat.st_mtime)
        )
        
    except Exception as e:
        logger.error(f"Failed to read file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")


@router.post("/content")
async def write_file_content(path: str, content: str, encoding: str = "utf-8"):
    """Write content to file."""
    try:
        file_path = validate_path(path)
        
        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write content
        file_path.write_text(content, encoding=encoding)
        
        stat = file_path.stat()
        
        return {
            "message": "File written successfully",
            "path": str(file_path.relative_to(get_workspace_root())),
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime)
        }
        
    except Exception as e:
        logger.error(f"Failed to write file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to write file: {str(e)}")


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), path: str = ""):
    """Upload a file."""
    try:
        # Determine target path
        if path:
            target_path = validate_path(path)
            if target_path.is_dir():
                target_path = target_path / file.filename
        else:
            target_path = get_workspace_root() / file.filename
        
        # Validate final path
        target_path = validate_path(str(target_path.relative_to(get_workspace_root())))
        
        # Create parent directories
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        content = await file.read()
        target_path.write_bytes(content)
        
        stat = target_path.stat()
        
        return {
            "message": "File uploaded successfully",
            "path": str(target_path.relative_to(get_workspace_root())),
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime)
        }
        
    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.get("/download")
async def download_file(path: str):
    """Download a file."""
    try:
        file_path = validate_path(path)
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")
        
        return FileResponse(
            path=str(file_path),
            filename=file_path.name,
            media_type='application/octet-stream'
        )
        
    except Exception as e:
        logger.error(f"Failed to download file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")


@router.delete("/")
async def delete_file(path: str):
    """Delete a file or directory."""
    try:
        file_path = validate_path(path)
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File or directory not found")
        
        if file_path.is_dir():
            # Remove directory and contents
            import shutil
            shutil.rmtree(file_path)
            return {"message": f"Directory {path} deleted successfully"}
        else:
            # Remove file
            file_path.unlink()
            return {"message": f"File {path} deleted successfully"}
        
    except Exception as e:
        logger.error(f"Failed to delete: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete: {str(e)}")


@router.post("/mkdir")
async def create_directory(path: str):
    """Create a directory."""
    try:
        dir_path = validate_path(path)
        
        if dir_path.exists():
            raise HTTPException(status_code=400, detail="Directory already exists")
        
        dir_path.mkdir(parents=True, exist_ok=False)
        
        return {
            "message": f"Directory {path} created successfully",
            "path": str(dir_path.relative_to(get_workspace_root()))
        }
        
    except Exception as e:
        logger.error(f"Failed to create directory: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create directory: {str(e)}")


@router.post("/move")
async def move_file(source: str, destination: str):
    """Move/rename a file or directory."""
    try:
        source_path = validate_path(source)
        dest_path = validate_path(destination)
        
        if not source_path.exists():
            raise HTTPException(status_code=404, detail="Source not found")
        
        if dest_path.exists():
            raise HTTPException(status_code=400, detail="Destination already exists")
        
        # Create parent directory if needed
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Move file/directory
        source_path.rename(dest_path)
        
        return {
            "message": f"Moved {source} to {destination}",
            "source": source,
            "destination": destination
        }
        
    except Exception as e:
        logger.error(f"Failed to move: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to move: {str(e)}")


@router.post("/copy")
async def copy_file(source: str, destination: str):
    """Copy a file or directory."""
    try:
        source_path = validate_path(source)
        dest_path = validate_path(destination)
        
        if not source_path.exists():
            raise HTTPException(status_code=404, detail="Source not found")
        
        if dest_path.exists():
            raise HTTPException(status_code=400, detail="Destination already exists")
        
        # Create parent directory if needed
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        if source_path.is_dir():
            import shutil
            shutil.copytree(source_path, dest_path)
        else:
            import shutil
            shutil.copy2(source_path, dest_path)
        
        return {
            "message": f"Copied {source} to {destination}",
            "source": source,
            "destination": destination
        }
        
    except Exception as e:
        logger.error(f"Failed to copy: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to copy: {str(e)}")


@router.get("/info", response_model=FileInfo)
async def get_file_info(path: str):
    """Get file or directory information."""
    try:
        file_path = validate_path(path)
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File or directory not found")
        
        stat = file_path.stat()
        
        return FileInfo(
            path=str(file_path.relative_to(get_workspace_root())),
            size=stat.st_size,
            modified=datetime.fromtimestamp(stat.st_mtime),
            is_directory=file_path.is_dir(),
            permissions=oct(stat.st_mode)[-3:]
        )
        
    except Exception as e:
        logger.error(f"Failed to get file info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get file info: {str(e)}")