"""Pydantic models for API requests and responses."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from agent.orchestrator.state import ExecutionStatus
from agent.planning.cost_estimator import ApprovalLevel, RiskLevel
from agent.planning.modes import PlanningMode


class TaskRequest(BaseModel):
    """Request to execute a task."""
    instruction: str = Field(..., description="The task instruction")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    planning_mode: Optional[PlanningMode] = Field(None, description="Specific planning mode")
    target_files: Optional[List[str]] = Field(None, description="Target files for the task")
    generate_preview: bool = Field(True, description="Whether to generate preview")
    estimate_cost: bool = Field(True, description="Whether to estimate cost")
    dry_run: bool = Field(False, description="Execute in dry run mode")
    auto_approve: bool = Field(False, description="Auto-approve low-risk tasks")


class TaskResponse(BaseModel):
    """Response from task execution request."""
    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Current task status")
    message: str = Field(..., description="Status message")
    requires_approval: bool = Field(False, description="Whether task requires approval")
    approval_message: Optional[str] = Field(None, description="Approval request message")
    preview_url: Optional[str] = Field(None, description="URL to task preview")


class TaskStatus(BaseModel):
    """Task status information."""
    task_id: str
    instruction: str
    status: ExecutionStatus
    progress: Dict[str, Any]
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_step: Optional[str] = None
    error_message: Optional[str] = None


class TaskPreview(BaseModel):
    """Task execution preview."""
    task_id: str
    title: str
    description: str
    mode: PlanningMode
    estimated_time_minutes: float
    complexity_score: float
    risk_level: RiskLevel
    approval_required: ApprovalLevel
    files_affected: List[str]
    commands_to_run: List[str]
    step_summaries: List[str]
    potential_risks: List[str]
    expected_outcomes: List[str]


class ApprovalRequest(BaseModel):
    """Approval request for task execution."""
    task_id: str
    message: str
    approval_level: ApprovalLevel
    cost_summary: Dict[str, Any]
    safety_concerns: List[str]
    timeout_seconds: int = 300


class ApprovalResponse(BaseModel):
    """Response to approval request."""
    task_id: str
    approved: bool
    response_message: Optional[str] = None


class StreamEvent(BaseModel):
    """Streaming event from task execution."""
    event_type: str
    task_id: str
    timestamp: datetime
    data: Dict[str, Any]


class FileInfo(BaseModel):
    """File information."""
    path: str
    size: int
    modified: datetime
    is_directory: bool
    permissions: str


class DirectoryListing(BaseModel):
    """Directory listing response."""
    path: str
    files: List[FileInfo]
    directories: List[FileInfo]
    total_files: int
    total_directories: int


class FileContent(BaseModel):
    """File content response."""
    path: str
    content: str
    encoding: str
    size: int
    modified: datetime


class ProjectInfo(BaseModel):
    """Project information."""
    id: str
    name: str
    description: str
    workspace_path: str
    created_at: datetime
    updated_at: datetime
    is_current: bool
    memory_count: int
    file_patterns: List[str]
    dependencies: List[str]


class ConversationInfo(BaseModel):
    """Conversation session information."""
    id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    project_id: Optional[str] = None
    is_current: bool


class ChatMessage(BaseModel):
    """Chat message."""
    role: str = Field(..., description="Message role (user/assistant/system)")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    """Chat request."""
    message: str = Field(..., description="User message")
    session_id: Optional[str] = Field(None, description="Session ID")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    stream: bool = Field(False, description="Stream response")


class ChatResponse(BaseModel):
    """Chat response."""
    message: str
    session_id: str
    message_id: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


class SystemStatus(BaseModel):
    """System status information."""
    status: str
    version: str
    uptime_seconds: float
    active_tasks: int
    total_tasks_completed: int
    memory_usage_mb: float
    workspace_path: str
    bedrock_status: str
    vector_index_status: str
    memory_stats: Dict[str, Any]


class HealthCheck(BaseModel):
    """Health check response."""
    status: str
    timestamp: datetime
    services: Dict[str, str]
    version: str


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime


class SearchRequest(BaseModel):
    """Search request."""
    query: str = Field(..., description="Search query")
    search_type: str = Field("all", description="Type of search (code, memory, files, all)")
    max_results: int = Field(10, description="Maximum results to return")
    project_id: Optional[str] = Field(None, description="Project to search in")
    file_patterns: Optional[List[str]] = Field(None, description="File patterns to include")


class SearchResult(BaseModel):
    """Search result item."""
    type: str  # code, memory, file
    title: str
    content: str
    path: Optional[str] = None
    score: float
    metadata: Dict[str, Any]


class SearchResponse(BaseModel):
    """Search response."""
    query: str
    results: List[SearchResult]
    total_results: int
    search_time_ms: float


class ConfigUpdate(BaseModel):
    """Configuration update request."""
    key: str
    value: Any
    description: Optional[str] = None


class ConfigResponse(BaseModel):
    """Configuration response."""
    config: Dict[str, Any]
    editable_keys: List[str]
    descriptions: Dict[str, str]