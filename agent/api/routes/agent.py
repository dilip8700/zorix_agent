"""Agent routes for task planning and execution."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/plan")
async def plan_task():
    """Plan a coding task - placeholder."""
    return JSONResponse(
        content={"message": "Planning endpoint - coming soon"},
        status_code=501
    )


@router.post("/apply")
async def apply_plan():
    """Apply a plan - placeholder."""
    return JSONResponse(
        content={"message": "Apply endpoint - coming soon"},
        status_code=501
    )


@router.post("/execute")
async def execute_task():
    """Execute a task - placeholder."""
    return JSONResponse(
        content={"message": "Execute endpoint - coming soon"},
        status_code=501
    )