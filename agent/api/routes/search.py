"""Search routes for code and memory search."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/")
async def search_content():
    """Search content - placeholder."""
    return JSONResponse(
        content={"message": "Search endpoint - coming soon"},
        status_code=501
    )


@router.post("/code")
async def search_code():
    """Search code - placeholder."""
    return JSONResponse(
        content={"message": "Code search endpoint - coming soon"},
        status_code=501
    )


@router.post("/memory")
async def search_memory():
    """Search memory - placeholder."""
    return JSONResponse(
        content={"message": "Memory search endpoint - coming soon"},
        status_code=501
    )