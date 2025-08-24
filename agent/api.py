"""Zorix Agent FastAPI application."""

import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn

from agent.config import get_settings
from agent.orchestrator import AgentOrchestrator
from agent.memory.provider import MemoryProvider
from agent.vector.index import VectorIndex
from agent.llm.bedrock_client import BedrockClient
from agent.tools.filesystem import FilesystemTools
from agent.tools.command import CommandTools
from agent.tools.git import GitTools

logger = logging.getLogger(__name__)

# Global app state
app_state: Dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Zorix Agent API...")
    
    try:
        # Initialize components
        settings = get_settings()
        
        # Initialize Bedrock client
        bedrock_client = BedrockClient()
        app_state["bedrock_client"] = bedrock_client
        logger.info("Bedrock client initialized successfully")
        
        # Initialize vector index
        vector_index = VectorIndex(workspace_root=settings.workspace_root)
        app_state["vector_index"] = vector_index
        logger.info("Vector index initialized successfully")
        
        # Initialize memory provider
        memory_provider = MemoryProvider()
        app_state["memory_provider"] = memory_provider
        logger.info("Memory provider initialized successfully")
        
        # Initialize tools
        filesystem_tools = FilesystemTools(workspace_root=settings.workspace_root)
        command_tools = CommandTools(workspace_root=settings.workspace_root)
        git_tools = GitTools(workspace_root=settings.workspace_root)
        
        app_state["filesystem_tools"] = filesystem_tools
        app_state["command_tools"] = command_tools
        app_state["git_tools"] = git_tools
        logger.info("Tools initialized successfully")
        
        # Initialize orchestrator
        orchestrator = AgentOrchestrator(
            bedrock_client=bedrock_client,
            memory_provider=memory_provider,
            vector_index=vector_index,
            filesystem_tools=filesystem_tools,
            command_tools=command_tools,
            git_tools=git_tools
        )
        app_state["orchestrator"] = orchestrator
        logger.info("Orchestrator initialized successfully")
        
        logger.info("Zorix Agent API started successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize API: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Zorix Agent API...")
    
    # Close Bedrock client
    if "bedrock_client" in app_state:
        await app_state["bedrock_client"].close()
    
    logger.info("Zorix Agent API shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Zorix Agent",
    description="AI-powered development agent using AWS Bedrock",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


# Agent planning endpoint
@app.post("/agent/plan")
async def create_plan(request: dict):
    """Create an execution plan from an instruction."""
    try:
        orchestrator = app_state.get("orchestrator")
        if not orchestrator:
            raise HTTPException(status_code=503, detail="Orchestrator not available")
        
        # Extract request parameters
        message = request.get("message", "")
        mode = request.get("mode", "auto")
        budget = request.get("budget", {})
        auto_apply = request.get("auto_apply", False)
        
        if not message:
            raise HTTPException(status_code=400, detail="Message is required")
        
        # Create plan
        plan_result = await orchestrator.create_plan(
            instruction=message,
            mode=mode,
            budget=budget,
            auto_apply=auto_apply
        )
        
        return plan_result
        
    except Exception as e:
        logger.error(f"Failed to create plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Agent apply endpoint
@app.post("/agent/apply")
async def apply_plan(request: dict):
    """Apply a previously created plan."""
    try:
        orchestrator = app_state.get("orchestrator")
        if not orchestrator:
            raise HTTPException(status_code=503, detail="Orchestrator not available")
        
        plan = request.get("plan")
        approve_all = request.get("approve_all", False)
        
        if not plan:
            raise HTTPException(status_code=400, detail="Plan is required")
        
        # Apply plan
        result = await orchestrator.apply_plan(plan, approve_all=approve_all)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to apply plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Agent chat endpoint (streaming)
@app.post("/agent/chat")
async def chat_stream(request: dict):
    """Streaming chat endpoint with tool calling."""
    try:
        orchestrator = app_state.get("orchestrator")
        if not orchestrator:
            raise HTTPException(status_code=503, detail="Orchestrator not available")
        
        messages = request.get("messages", [])
        tools_allow = request.get("tools_allow", [])
        mode = request.get("mode", "auto")
        
        if not messages:
            raise HTTPException(status_code=400, detail="Messages are required")
        
        # Stream response
        async def generate():
            async for chunk in orchestrator.chat_stream(messages, tools_allow, mode):
                yield f"data: {chunk}\n\n"
        
        return StreamingResponse(generate(), media_type="text/event-stream")
        
    except Exception as e:
        logger.error(f"Failed to start chat stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Search endpoint
@app.post("/search")
async def search_code(request: dict):
    """Search code using vector index."""
    try:
        vector_index = app_state.get("vector_index")
        if not vector_index:
            raise HTTPException(status_code=503, detail="Vector index not available")
        
        query = request.get("query", "")
        top_k = request.get("top_k", 20)
        
        if not query:
            raise HTTPException(status_code=400, detail="Query is required")
        
        # Search
        results = await vector_index.search(query, top_k=top_k)
        
        return {"results": results}
        
    except Exception as e:
        logger.error(f"Failed to search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Git endpoints
@app.post("/git/status")
async def git_status():
    """Get git status."""
    try:
        git_tools = app_state.get("git_tools")
        if not git_tools:
            raise HTTPException(status_code=503, detail="Git tools not available")
        
        status = await git_tools.git_status()
        return status
        
    except Exception as e:
        logger.error(f"Failed to get git status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/git/diff")
async def git_diff(request: dict):
    """Get git diff."""
    try:
        git_tools = app_state.get("git_tools")
        if not git_tools:
            raise HTTPException(status_code=503, detail="Git tools not available")
        
        rev = request.get("rev")
        diff = await git_tools.git_diff(rev)
        return {"diff": diff}
        
    except Exception as e:
        logger.error(f"Failed to get git diff: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/git/commit")
async def git_commit(request: dict):
    """Create git commit."""
    try:
        git_tools = app_state.get("git_tools")
        if not git_tools:
            raise HTTPException(status_code=503, detail="Git tools not available")
        
        message = request.get("message", "")
        add_all = request.get("add_all", True)
        
        if not message:
            raise HTTPException(status_code=400, detail="Commit message is required")
        
        result = await git_tools.git_commit(message, add_all=add_all)
        return result
        
    except Exception as e:
        logger.error(f"Failed to create commit: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/git/branch")
async def git_branch(request: dict):
    """Git branch operations."""
    try:
        git_tools = app_state.get("git_tools")
        if not git_tools:
            raise HTTPException(status_code=503, detail="Git tools not available")
        
        name = request.get("name")
        result = await git_tools.git_branch(name)
        return result
        
    except Exception as e:
        logger.error(f"Failed to perform branch operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/git/checkout")
async def git_checkout(request: dict):
    """Git checkout."""
    try:
        git_tools = app_state.get("git_tools")
        if not git_tools:
            raise HTTPException(status_code=503, detail="Git tools not available")
        
        ref = request.get("ref")
        if not ref:
            raise HTTPException(status_code=400, detail="Reference is required")
        
        result = await git_tools.git_checkout(ref)
        return result
        
    except Exception as e:
        logger.error(f"Failed to checkout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Index rebuild endpoint
@app.post("/index/rebuild")
async def rebuild_index():
    """Rebuild the vector index."""
    try:
        vector_index = app_state.get("vector_index")
        if not vector_index:
            raise HTTPException(status_code=503, detail="Vector index not available")
        
        stats = await vector_index.build_index()
        return {"ok": True, "stats": stats}
        
    except Exception as e:
        logger.error(f"Failed to rebuild index: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(
        "agent.api:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
