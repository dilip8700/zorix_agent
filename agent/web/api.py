"""FastAPI application factory and configuration."""

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from agent.config import get_settings
from agent.llm.bedrock_client import BedrockClient
from agent.memory.provider import MemoryProvider
from agent.orchestrator.core import AgentOrchestrator
from agent.planning.planner import TaskPlanner
from agent.planning.executor import PlanExecutor
from agent.vector.index import VectorIndex
from agent.web.models import ErrorResponse
from agent.web.routes import (
    chat_router,
    files_router,
    projects_router,
    search_router,
    system_router,
    tasks_router,
)
from agent.web.streaming import streaming_manager
from agent.observability import configure_logging, configure_tracing, get_logger, get_metrics_collector

logger = logging.getLogger(__name__)

# Global application state
app_state: Dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    settings = get_settings()
    
    # Configure observability
    configure_logging(
        level=settings.log_level,
        format_type=settings.log_format,
        log_file=settings.log_file,
        context={"service": "zorix-agent-api", "version": "1.0.0"}
    )
    
    if settings.enable_tracing:
        configure_tracing(
            service_name="zorix-agent-api",
            service_version="1.0.0",
            otlp_endpoint=settings.otel_exporter_otlp_endpoint,
            console_export=settings.log_level == "DEBUG"
        )
    
    logger = get_logger("agent.web.api")
    metrics = get_metrics_collector()
    
    logger.info("Starting Zorix Agent API...")
    metrics.increment_counter("api_starts")
    
    try:
        # Initialize core components
        bedrock_client = BedrockClient()
        
        # Initialize vector index
        vector_index = VectorIndex(
            index_path=Path(settings.vector_index_path),
            workspace_root=Path(settings.workspace_root)
        )
        
        # Initialize memory provider
        memory_provider = MemoryProvider(
            storage_path=Path(settings.memory_db_path),
            bedrock_client=bedrock_client,
            vector_index=vector_index,
            workspace_root=settings.workspace_root
        )
        
        # Initialize orchestrator
        orchestrator = AgentOrchestrator(
            bedrock_client=bedrock_client,
            memory_provider=memory_provider,
            workspace_root=settings.workspace_root
        )
        
        # Initialize enhanced planner
        planner = TaskPlanner(
            bedrock_client=bedrock_client,
            memory_provider=memory_provider
        )
        
        # Initialize enhanced executor
        executor = PlanExecutor(
            bedrock_client=bedrock_client,
            memory_provider=memory_provider,
            workspace_root=settings.workspace_root
        )
        
        # Start streaming manager
        await streaming_manager.start()
        
        # Store in app state
        app_state.update({
            "settings": settings,
            "bedrock_client": bedrock_client,
            "vector_index": vector_index,
            "memory_provider": memory_provider,
            "orchestrator": orchestrator,
            "planner": planner,
            "executor": executor,
            "start_time": time.time(),
            "task_counter": 0,
            "completed_tasks": 0,
        })
        
        logger.info("Zorix Agent API started successfully")
        metrics.set_gauge("api_status", 1.0)
        
    except Exception as e:
        logger.error(f"Failed to start Zorix Agent API: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Zorix Agent API...")
    metrics.set_gauge("api_status", 0.0)
    metrics.increment_counter("api_shutdowns")
    
    # Stop streaming manager
    await streaming_manager.stop()
    
    # Cleanup resources
    if "bedrock_client" in app_state:
        await app_state["bedrock_client"].close()
    
    logger.info("Zorix Agent API shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    app = FastAPI(
        title="Zorix Agent API",
        description="AI-powered development agent with advanced planning and execution capabilities",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )
    
    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Add observability middleware
    @app.middleware("http")
    async def observability_middleware(request: Request, call_next):
        start_time = time.time()
        logger = get_logger("agent.web.middleware")
        metrics = get_metrics_collector()
        
        # Log request
        logger.info(
            "HTTP request started",
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else None
        )
        
        # Increment request counter
        metrics.increment_counter(
            "http_requests_total",
            1,
            {"method": request.method, "path": request.url.path}
        )
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # Record metrics
            metrics.record_timer(
                "http_request_duration",
                process_time,
                {"method": request.method, "status": str(response.status_code)}
            )
            
            metrics.increment_counter(
                "http_responses_total",
                1,
                {"method": request.method, "status": str(response.status_code)}
            )
            
            # Log response
            logger.info(
                "HTTP request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=process_time * 1000
            )
            
            # Add timing header
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            
            # Record error metrics
            metrics.increment_counter(
                "http_errors_total",
                1,
                {"method": request.method, "error_type": type(e).__name__}
            )
            
            # Log error
            logger.error(
                "HTTP request failed",
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_ms=process_time * 1000,
                exc_info=True
            )
            
            raise
    
    # Add error handling
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=exc.__class__.__name__,
                message=exc.detail,
                timestamp=time.time()
            ).dict()
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=exc.__class__.__name__,
                message="Internal server error",
                details={"exception": str(exc)},
                timestamp=time.time()
            ).dict()
        )
    
    # Include routers
    app.include_router(system_router, prefix="/api/v1/system", tags=["System"])
    app.include_router(tasks_router, prefix="/api/v1/tasks", tags=["Tasks"])
    app.include_router(chat_router, prefix="/api/v1/chat", tags=["Chat"])
    app.include_router(files_router, prefix="/api/v1/files", tags=["Files"])
    app.include_router(projects_router, prefix="/api/v1/projects", tags=["Projects"])
    app.include_router(search_router, prefix="/api/v1/search", tags=["Search"])
    
    # Serve static files (web interface)
    static_path = Path(__file__).parent / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
    
    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "Zorix Agent API",
            "version": "1.0.0",
            "description": "AI-powered development agent",
            "docs_url": "/docs",
            "health_url": "/api/v1/system/health",
            "status_url": "/api/v1/system/status"
        }
    
    return app


def get_app_state() -> Dict[str, Any]:
    """Get current application state."""
    return app_state