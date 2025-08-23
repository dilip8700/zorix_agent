"""FastAPI application for Zorix Agent."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agent.config import get_settings

# Get settings
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="Zorix Agent",
    description="AI-powered coding assistant backend using AWS Bedrock",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        content={
            "status": "ok",
            "service": "zorix-agent",
            "version": "0.1.0",
            "workspace": str(settings.workspace_root),
            "bedrock_region": settings.bedrock_region
        }
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return JSONResponse(
        content={
            "message": "Zorix Agent API",
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/healthz"
        }
    )


# Placeholder endpoints - will be implemented in later tasks
@app.post("/agent/plan")
async def plan_task():
    """Plan a coding task - placeholder."""
    return JSONResponse(
        content={"message": "Planning endpoint - coming soon"},
        status_code=501
    )


@app.post("/agent/apply")
async def apply_plan():
    """Apply a plan - placeholder."""
    return JSONResponse(
        content={"message": "Apply endpoint - coming soon"},
        status_code=501
    )


@app.post("/agent/chat")
async def chat_stream():
    """Streaming chat - placeholder."""
    return JSONResponse(
        content={"message": "Chat endpoint - coming soon"},
        status_code=501
    )


@app.post("/search")
async def search_code():
    """Search code - placeholder."""
    return JSONResponse(
        content={"message": "Search endpoint - coming soon"},
        status_code=501
    )


@app.post("/index/rebuild")
async def rebuild_index():
    """Rebuild vector index - placeholder."""
    return JSONResponse(
        content={"message": "Index rebuild endpoint - coming soon"},
        status_code=501
    )


# Git operation placeholders
@app.post("/git/status")
async def git_status():
    """Git status - placeholder."""
    return JSONResponse(
        content={"message": "Git status endpoint - coming soon"},
        status_code=501
    )


@app.post("/git/diff")
async def git_diff():
    """Git diff - placeholder."""
    return JSONResponse(
        content={"message": "Git diff endpoint - coming soon"},
        status_code=501
    )


@app.post("/git/commit")
async def git_commit():
    """Git commit - placeholder."""
    return JSONResponse(
        content={"message": "Git commit endpoint - coming soon"},
        status_code=501
    )


@app.post("/git/branch")
async def git_branch():
    """Git branch - placeholder."""
    return JSONResponse(
        content={"message": "Git branch endpoint - coming soon"},
        status_code=501
    )


@app.post("/git/checkout")
async def git_checkout():
    """Git checkout - placeholder."""
    return JSONResponse(
        content={"message": "Git checkout endpoint - coming soon"},
        status_code=501
    )