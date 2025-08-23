"""Base models and common types for Zorix Agent."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


class BaseZorixModel(BaseModel):
    """Base model for all Zorix Agent data structures."""
    
    class Config:
        # Enable validation on assignment
        validate_assignment = True
        # Use enum values instead of names
        use_enum_values = True
        # Allow population by field name or alias
        allow_population_by_field_name = True
        # Generate schema with examples
        schema_extra = {
            "examples": []
        }


class TaskMode(str, Enum):
    """Task execution modes."""
    EDIT = "edit"
    EXPLAIN = "explain"
    REFACTOR = "refactor"
    TEST = "test"
    CREATE = "create"
    REVIEW = "review"


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepType(str, Enum):
    """Types of plan steps."""
    TOOL_CALL = "tool_call"
    REASONING = "reasoning"
    APPROVAL = "approval"
    OBSERVATION = "observation"


class MessageRole(str, Enum):
    """Message roles in conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ErrorType(str, Enum):
    """Types of errors that can occur."""
    VALIDATION_ERROR = "validation_error"
    SECURITY_ERROR = "security_error"
    NOT_FOUND_ERROR = "not_found_error"
    CONFLICT_ERROR = "conflict_error"
    EXTERNAL_SERVICE_ERROR = "external_service_error"
    INTERNAL_ERROR = "internal_error"


class Message(BaseZorixModel):
    """A message in the conversation."""
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('content')
    def content_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Message content cannot be empty')
        return v.strip()


class ToolCall(BaseZorixModel):
    """A tool call request from the LLM."""
    id: str = Field(..., description="Unique identifier for the tool call")
    name: str = Field(..., description="Name of the tool to call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    
    @validator('name')
    def name_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Tool name cannot be empty')
        return v.strip()


class ToolResult(BaseZorixModel):
    """Result of a tool execution."""
    tool_call_id: str = Field(..., description="ID of the tool call this result is for")
    success: bool = Field(..., description="Whether the tool execution was successful")
    result: Any = Field(None, description="Tool execution result")
    error: Optional[str] = Field(None, description="Error message if execution failed")
    duration_ms: Optional[int] = Field(None, description="Execution duration in milliseconds")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CostEstimate(BaseZorixModel):
    """Cost estimation for a task or plan."""
    estimated_tokens: int = Field(..., ge=0, description="Estimated token usage")
    estimated_cost_usd: float = Field(..., ge=0, description="Estimated cost in USD")
    confidence: float = Field(..., ge=0, le=1, description="Confidence in the estimate")
    breakdown: Dict[str, Any] = Field(default_factory=dict, description="Cost breakdown")


class FileChange(BaseZorixModel):
    """Represents a change to a file."""
    path: str = Field(..., description="File path relative to workspace")
    operation: str = Field(..., description="Type of operation (create, modify, delete)")
    size_before: Optional[int] = Field(None, description="File size before change")
    size_after: Optional[int] = Field(None, description="File size after change")
    lines_added: Optional[int] = Field(None, description="Number of lines added")
    lines_removed: Optional[int] = Field(None, description="Number of lines removed")
    summary: Optional[str] = Field(None, description="Summary of changes")


class CommandResult(BaseZorixModel):
    """Result of command execution."""
    command: str = Field(..., description="Command that was executed")
    exit_code: int = Field(..., description="Command exit code")
    stdout: str = Field(default="", description="Standard output")
    stderr: str = Field(default="", description="Standard error")
    duration: float = Field(..., ge=0, description="Execution duration in seconds")
    success: bool = Field(..., description="Whether command executed successfully")
    working_directory: str = Field(..., description="Working directory where command was run")
    timeout: bool = Field(default=False, description="Whether command timed out")
    error: Optional[str] = Field(None, description="Error message if execution failed")


class GitOperation(BaseZorixModel):
    """Represents a git operation."""
    operation: str = Field(..., description="Type of git operation")
    success: bool = Field(..., description="Whether operation was successful")
    result: Dict[str, Any] = Field(default_factory=dict, description="Operation result")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class SearchResult(BaseZorixModel):
    """A search result from vector or text search."""
    path: str = Field(..., description="File path")
    start_line: int = Field(..., ge=1, description="Starting line number")
    end_line: int = Field(..., ge=1, description="Ending line number")
    snippet: str = Field(..., description="Code snippet")
    score: float = Field(..., ge=0, le=1, description="Relevance score")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('end_line')
    def end_line_after_start(cls, v, values):
        if 'start_line' in values and v < values['start_line']:
            raise ValueError('end_line must be >= start_line')
        return v


class ErrorResponse(BaseZorixModel):
    """Standard error response format."""
    error_type: ErrorType = Field(..., description="Type of error")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    suggestion: Optional[str] = Field(None, description="Suggested resolution")
    retry_after: Optional[int] = Field(None, description="Seconds to wait before retry")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthStatus(BaseZorixModel):
    """Health check response."""
    status: str = Field(..., description="Overall health status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    checks: Dict[str, Any] = Field(default_factory=dict, description="Individual health checks")
    workspace: Optional[str] = Field(None, description="Workspace path")
    bedrock_region: Optional[str] = Field(None, description="AWS Bedrock region")


class PaginationParams(BaseZorixModel):
    """Pagination parameters for list endpoints."""
    page: int = Field(1, ge=1, description="Page number (1-based)")
    page_size: int = Field(20, ge=1, le=100, description="Number of items per page")
    
    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseZorixModel):
    """Paginated response wrapper."""
    items: List[Any] = Field(..., description="List of items")
    total: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Items per page")
    total_pages: int = Field(default=0, ge=0, description="Total number of pages")
    has_next: bool = Field(default=False, description="Whether there are more pages")
    has_prev: bool = Field(default=False, description="Whether there are previous pages")
    
    def __init__(self, **data):
        # Calculate computed fields before validation
        if 'total_pages' not in data and 'total' in data and 'page_size' in data:
            data['total_pages'] = max(1, (data['total'] + data['page_size'] - 1) // data['page_size'])
        
        if 'has_next' not in data and 'page' in data and 'total_pages' in data:
            data['has_next'] = data['page'] < data['total_pages']
        
        if 'has_prev' not in data and 'page' in data:
            data['has_prev'] = data['page'] > 1
        
        super().__init__(**data)