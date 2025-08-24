"""Index routes for vector search operations."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/rebuild")
async def rebuild_index():
    """Rebuild vector index - placeholder."""
    return JSONResponse(
        content={"message": "Index rebuild endpoint - coming soon"},
        status_code=501
    )


@router.get("/status")
async def index_status():
    """Get index status - placeholder."""
    return JSONResponse(
        content={"message": "Index status endpoint - coming soon"},
        status_code=501
    )