"""
Centralized Models for Zorix Agent

This file contains ALL Pydantic models used throughout the system
to avoid circular imports and provide a single source of truth.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# CORE SYSTEM MODELS
# ============================================================================

class SystemStatus(BaseModel):
    """System status response model."""
    status: str = "healthy"
    uptime_seconds: float
    bedrock_status: str = "healthy"
    vector_index_status: str = "healthy"
    memory_status: str = "healthy"
    active_tasks: int = 0
    completed_tasks: int = 0
    memory_usage_mb: float = 0.0
    timestamp: float


class HealthCheck(BaseModel):
    """Health check response model."""
    status: str = "healthy"
    timestamp: float


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str


# ============================================================================
# AGENT PLANNING MODELS
# ============================================================================

class PlanRequest(BaseModel):
    """Request model for /agent/plan endpoint."""
    message: str = Field(..., description="Natural language instruction")
    mode: Optional[str] = Field("edit", description="Planning mode: edit|explain|refactor|test|create|review")
    budget: Optional[Dict[str, int]] = Field(None, description="Resource budget constraints")
    auto_apply: Optional[bool] = Field(False, description="Whether to auto-apply the plan")


class PlanStep(BaseModel):
    """Individual step in an execution plan."""
    step_type: str = Field(..., description="Type of step: tool_call, decision, etc.")
    tool: Optional[str] = Field(None, description="Tool to use for this step")
    args: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool")
    rationale: str = Field(..., description="Why this step is needed")
    expected_outcome: Optional[str] = Field(None, description="Expected result")


class PlanPreview(BaseModel):
    """Preview of changes that will be made."""
    files: List[Dict[str, str]] = Field(default_factory=list, description="Files that will be changed")
    commands: List[str] = Field(default_factory=list, description="Commands that will be run")
    git_operations: List[str] = Field(default_factory=list, description="Git operations")


class CostEstimate(BaseModel):
    """Cost estimate for plan execution."""
    estimated_tokens: int = 0
    estimated_time_seconds: int = 0
    risk_level: str = "low"  # low, medium, high
    requires_approval: bool = False


class PlanResponse(BaseModel):
    """Response model for /agent/plan endpoint."""
    plan_id: str = Field(..., description="Unique identifier for this plan")
    plan: List[PlanStep] = Field(..., description="List of execution steps")
    preview: PlanPreview = Field(..., description="Preview of changes")
    cost_estimate: CostEstimate = Field(..., description="Cost and risk estimate")
    requires_approval: bool = Field(False, description="Whether plan needs approval")
    message: str = Field("Plan created successfully", description="Status message")


# ============================================================================
# AGENT EXECUTION MODELS
# ============================================================================

class ApplyRequest(BaseModel):
    """Request model for /agent/apply endpoint."""
    plan_id: Optional[str] = Field(None, description="ID of plan to apply")
    plan: Optional[List[PlanStep]] = Field(None, description="Direct plan to apply")
    approve_all: Optional[bool] = Field(False, description="Auto-approve all steps")


class ExecutionResult(BaseModel):
    """Result of executing a single step."""
    step_id: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: float = 0.0


class ApplyResponse(BaseModel):
    """Response model for /agent/apply endpoint."""
    execution_id: str = Field(..., description="Unique execution identifier")
    applied: List[ExecutionResult] = Field(..., description="Results of applied steps")
    commands: List[Dict[str, Any]] = Field(default_factory=list, description="Commands executed")
    git: Optional[Dict[str, Any]] = Field(None, description="Git operations performed")
    success: bool = Field(True, description="Whether execution was successful")
    message: str = Field("Plan applied successfully", description="Status message")


# ============================================================================
# CHAT MODELS
# ============================================================================

class ChatMessage(BaseModel):
    """Individual chat message."""
    role: str = Field(..., description="Message role: user, assistant, system, tool")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    """Request model for chat endpoints."""
    messages: List[ChatMessage] = Field(..., description="Conversation history")
    tools_allow: Optional[List[str]] = Field(None, description="Allowed tools for this chat")
    mode: Optional[str] = Field("create", description="Chat mode: explain|edit|create|review")
    stream: Optional[bool] = Field(False, description="Whether to stream response")
    session_id: Optional[str] = Field(None, description="Session identifier")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class ChatResponse(BaseModel):
    """Response model for chat endpoints."""
    message: str = Field(..., description="Assistant response")
    session_id: str = Field(..., description="Session identifier")
    message_id: str = Field(..., description="Unique message identifier")
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None


# ============================================================================
# SEARCH MODELS
# ============================================================================

class SearchRequest(BaseModel):
    """Request model for search endpoints."""
    query: str = Field(..., description="Search query")
    top_k: Optional[int] = Field(20, description="Maximum number of results")
    search_type: Optional[str] = Field("all", description="Type of search: all|code|memory|files")


class SearchResult(BaseModel):
    """Individual search result."""
    path: str = Field(..., description="File path")
    start: int = Field(0, description="Start line/character")
    end: int = Field(0, description="End line/character")
    snippet: str = Field(..., description="Code snippet")
    score: float = Field(0.0, description="Relevance score")


class SearchResponse(BaseModel):
    """Response model for search endpoints."""
    query: str = Field(..., description="Original search query")
    results: List[SearchResult] = Field(..., description="Search results")
    total_found: int = Field(0, description="Total number of results")
    search_time_ms: float = Field(0.0, description="Search execution time")


# ============================================================================
# FILE OPERATION MODELS
# ============================================================================

class FileRequest(BaseModel):
    """Request model for file operations."""
    path: str = Field(..., description="File path")
    content: Optional[str] = Field(None, description="File content")
    encoding: Optional[str] = Field("utf-8", description="File encoding")


class FileResponse(BaseModel):
    """Response model for file operations."""
    path: str = Field(..., description="File path")
    success: bool = Field(True, description="Whether operation succeeded")
    content: Optional[str] = Field(None, description="File content")
    size: Optional[int] = Field(None, description="File size in bytes")
    modified: Optional[datetime] = Field(None, description="Last modified time")
    error: Optional[str] = Field(None, description="Error message if failed")


class DirectoryListing(BaseModel):
    """Directory listing entry."""
    path: str = Field(..., description="Entry path")
    is_directory: bool = Field(False, description="Whether entry is a directory")
    size: Optional[int] = Field(None, description="File size")
    modified: Optional[datetime] = Field(None, description="Last modified time")


class DirectoryResponse(BaseModel):
    """Response model for directory listings."""
    path: str = Field(..., description="Directory path")
    entries: List[DirectoryListing] = Field(..., description="Directory entries")
    total_entries: int = Field(0, description="Total number of entries")


# ============================================================================
# GIT OPERATION MODELS
# ============================================================================

class GitStatusResponse(BaseModel):
    """Response model for git status."""
    modified: List[str] = Field(default_factory=list)
    added: List[str] = Field(default_factory=list)
    deleted: List[str] = Field(default_factory=list)
    untracked: List[str] = Field(default_factory=list)
    staged: List[str] = Field(default_factory=list)
    current_branch: Optional[str] = None


class GitCommitRequest(BaseModel):
    """Request model for git commit."""
    message: str = Field(..., description="Commit message")
    add_all: Optional[bool] = Field(True, description="Add all files before committing")
    files: Optional[List[str]] = Field(None, description="Specific files to commit")


class GitCommitResponse(BaseModel):
    """Response model for git commit."""
    commit_hash: str = Field(..., description="Generated commit hash")
    message: str = Field(..., description="Commit message")
    files_changed: int = Field(0, description="Number of files changed")


# ============================================================================
# TASK MANAGEMENT MODELS
# ============================================================================

class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskRequest(BaseModel):
    """Legacy task request model (for compatibility)."""
    instruction: str = Field(..., description="Task instruction")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    mode: Optional[str] = Field("edit", description="Execution mode")
    auto_approve: Optional[bool] = Field(False, description="Auto-approve execution")


class TaskPreview(BaseModel):
    """Task execution preview."""
    files_to_change: List[str] = Field(default_factory=list)
    commands_to_run: List[str] = Field(default_factory=list)
    estimated_duration: Optional[int] = None


class TaskResponse(BaseModel):
    """Legacy task response model (for compatibility)."""
    task_id: str = Field(..., description="Task identifier")
    status: TaskStatus = Field(TaskStatus.PENDING, description="Task status")
    message: str = Field("Task created", description="Status message")
    preview: Optional[TaskPreview] = None
    requires_approval: bool = Field(False, description="Whether task needs approval")


# ============================================================================
# APPROVAL MODELS
# ============================================================================

class ApprovalRequest(BaseModel):
    """Request model for task approval."""
    task_id: str = Field(..., description="Task to approve/reject")
    approved: bool = Field(..., description="Whether task is approved")
    message: Optional[str] = Field(None, description="Approval message")


class ApprovalResponse(BaseModel):
    """Response model for task approval."""
    task_id: str = Field(..., description="Task identifier")
    approved: bool = Field(..., description="Whether task was approved")
    message: str = Field("Approval processed", description="Response message")


# ============================================================================
# STREAMING MODELS
# ============================================================================

class StreamEventType(str, Enum):
    """Types of streaming events."""
    MESSAGE_START = "message_start"
    MESSAGE_DELTA = "message_delta"
    MESSAGE_COMPLETE = "message_complete"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_RESULT = "tool_call_result"
    ERROR = "error"
    STREAM_END = "stream_end"


class StreamEvent(BaseModel):
    """Streaming event model."""
    type: StreamEventType = Field(..., description="Event type")
    data: Optional[Dict[str, Any]] = Field(None, description="Event data")
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())


# ============================================================================
# INDEX MODELS
# ============================================================================

class IndexRebuildResponse(BaseModel):
    """Response model for index rebuild."""
    ok: bool = Field(True, description="Whether rebuild succeeded")
    stats: Dict[str, Any] = Field(..., description="Rebuild statistics")
    message: str = Field("Index rebuilt successfully", description="Status message")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # System models
    "SystemStatus", "HealthCheck", "ErrorResponse",
    
    # Planning models
    "PlanRequest", "PlanStep", "PlanPreview", "CostEstimate", "PlanResponse",
    
    # Execution models  
    "ApplyRequest", "ExecutionResult", "ApplyResponse",
    
    # Chat models
    "ChatMessage", "ChatRequest", "ChatResponse",
    
    # Search models
    "SearchRequest", "SearchResult", "SearchResponse",
    
    # File models
    "FileRequest", "FileResponse", "DirectoryListing", "DirectoryResponse",
    
    # Git models
    "GitStatusResponse", "GitCommitRequest", "GitCommitResponse",
    
    # Task models
    "TaskStatus", "TaskRequest", "TaskPreview", "TaskResponse",
    
    # Approval models
    "ApprovalRequest", "ApprovalResponse",
    
    # Streaming models
    "StreamEventType", "StreamEvent",
    
    # Index models
    "IndexRebuildResponse",
]
