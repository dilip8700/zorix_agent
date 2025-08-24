"""Chat routes for conversational interface."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/message")
async def send_message():
    """Send a chat message - placeholder."""
    return JSONResponse(
        content={"message": "Chat endpoint - coming soon"},
        status_code=501
    )


@router.get("/stream")
async def stream_chat():
    """Stream chat responses - placeholder."""
    return JSONResponse(
        content={"message": "Streaming chat endpoint - coming soon"},
        status_code=501
    )