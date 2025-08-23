"""API request and response models for Zorix Agent."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field, validator

from agent.models.base import BaseZorixModel, SearchResult
from agent.models.plan import Plan, ExecutionResult


class SearchRequest(BaseZorixModel):
    """Request to search code."""
    query: str = Field(..., description="Search query")
    top_k: int = Field(20, ge=1, le=100, description="Maximum number of results")
    file_types: Optional[List[str]] = Field(None, description="Filter by file extensions")
    include_hidden: bool = Field(False, description="Include hidden files")
    
    @validator('query')
    def query_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Search query cannot be empty')
        return v.strip()


class SearchResponse(BaseZorixModel):
    """Response from code search."""
    results: List[SearchResult] = Field(..., description="Search results")
    total_found: int = Field(..., ge=0, description="Total number of matches")
    query: str = Field(..., description="Original search query")
    duration_ms: int = Field(..., ge=0, description="Search duration")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PlanResponse(BaseZorixModel):
    """Response from plan generation."""
    plan: Plan = Field(..., description="Generated execution plan")
    warnings: List[str] = Field(default_factory=list, description="Warnings about the plan")
    suggestions: List[str] = Field(default_factory=list, description="Suggestions for improvement")
    duration_ms: int = Field(..., ge=0, description="Planning duration")


class ApplyResponse(BaseZorixModel):
    """Response from plan application."""
    execution_result: ExecutionResult = Field(..., description="Execution result")
    warnings: List[str] = Field(default_factory=list, description="Warnings during execution")
    duration_ms: int = Field(..., ge=0, description="Total application duration")


class GitStatusRequest(BaseZorixModel):
    """Request for git status."""
    include_untracked: bool = Field(True, description="Include untracked files")
    include_ignored: bool = Field(False, description="Include ignored files")


class GitStatusResponse(BaseZorixModel):
    """Response from git status."""
    modified: List[str] = Field(default_factory=list, description="Modified files")
    added: List[str] = Field(default_factory=list, description="Added files")
    deleted: List[str] = Field(default_factory=list, description="Deleted files")
    untracked: List[str] = Field(default_factory=list, description="Untracked files")
    ignored: List[str] = Field(default_factory=list, description="Ignored files")
    branch: str = Field(..., description="Current branch")
    is_clean: bool = Field(..., description="Whether working directory is clean")


class GitDiffRequest(BaseZorixModel):
    """Request for git diff."""
    revision: Optional[str] = Field(None, description="Revision to diff against")
    file_path: Optional[str] = Field(None, description="Specific file to diff")
    staged: bool = Field(False, description="Show staged changes only")


class GitDiffResponse(BaseZorixModel):
    """Response from git diff."""
    diff: str = Field(..., description="Diff output")
    files_changed: int = Field(..., ge=0, description="Number of files changed")
    insertions: int = Field(..., ge=0, description="Number of insertions")
    deletions: int = Field(..., ge=0, description="Number of deletions")


class GitCommitRequest(BaseZorixModel):
    """Request to create git commit."""
    message: str = Field(..., description="Commit message")
    add_all: bool = Field(True, description="Add all changes before committing")
    files: Optional[List[str]] = Field(None, description="Specific files to commit")
    
    @validator('message')
    def message_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Commit message cannot be empty')
        return v.strip()


class GitCommitResponse(BaseZorixModel):
    """Response from git commit."""
    commit_hash: str = Field(..., description="Hash of created commit")
    message: str = Field(..., description="Commit message")
    files_changed: int = Field(..., ge=0, description="Number of files changed")
    insertions: int = Field(..., ge=0, description="Number of insertions")
    deletions: int = Field(..., ge=0, description="Number of deletions")


class GitBranchRequest(BaseZorixModel):
    """Request for git branch operations."""
    name: Optional[str] = Field(None, description="Branch name to create")
    list_all: bool = Field(False, description="List all branches")


class GitBranchResponse(BaseZorixModel):
    """Response from git branch operations."""
    current: str = Field(..., description="Current branch name")
    branches: List[str] = Field(default_factory=list, description="All branches")
    created: Optional[str] = Field(None, description="Newly created branch")


class GitCheckoutRequest(BaseZorixModel):
    """Request to checkout git reference."""
    ref: str = Field(..., description="Branch, tag, or commit to checkout")
    create_branch: bool = Field(False, description="Create new branch if it doesn't exist")
    
    @validator('ref')
    def ref_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Git reference cannot be empty')
        return v.strip()


class GitCheckoutResponse(BaseZorixModel):
    """Response from git checkout."""
    current: str = Field(..., description="Current branch/ref after checkout")
    previous: str = Field(..., description="Previous branch/ref")
    created_branch: bool = Field(False, description="Whether a new branch was created")


class IndexRebuildRequest(BaseZorixModel):
    """Request to rebuild vector index."""
    force: bool = Field(False, description="Force rebuild even if index exists")
    file_patterns: Optional[List[str]] = Field(None, description="File patterns to include")
    exclude_patterns: Optional[List[str]] = Field(None, description="File patterns to exclude")


class IndexRebuildResponse(BaseZorixModel):
    """Response from index rebuild."""
    success: bool = Field(..., description="Whether rebuild was successful")
    stats: Dict[str, Any] = Field(..., description="Rebuild statistics")
    duration_ms: int = Field(..., ge=0, description="Rebuild duration")
    files_processed: int = Field(..., ge=0, description="Number of files processed")
    chunks_created: int = Field(..., ge=0, description="Number of chunks created")
    errors: List[str] = Field(default_factory=list, description="Errors encountered")


class StreamingResponse(BaseZorixModel):
    """Base class for streaming responses."""
    event: str = Field(..., description="Event type")
    data: Any = Field(None, description="Event data")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('event')
    def event_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Event type cannot be empty')
        return v.strip()


class TokenStreamEvent(StreamingResponse):
    """Token streaming event."""
    event: str = Field("token", description="Event type")
    data: str = Field(..., description="Token content")


class ToolCallStreamEvent(StreamingResponse):
    """Tool call streaming event."""
    event: str = Field("tool_call", description="Event type")
    data: Dict[str, Any] = Field(..., description="Tool call information")


class ErrorStreamEvent(StreamingResponse):
    """Error streaming event."""
    event: str = Field("error", description="Event type")
    data: Dict[str, Any] = Field(..., description="Error information")


class CompleteStreamEvent(StreamingResponse):
    """Completion streaming event."""
    event: str = Field("complete", description="Event type")
    data: Dict[str, Any] = Field(default_factory=dict, description="Completion information")


class ValidationError(BaseZorixModel):
    """Validation error details."""
    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Validation error message")
    value: Any = Field(None, description="Invalid value")


class ValidationErrorResponse(BaseZorixModel):
    """Response for validation errors."""
    error_type: str = Field("validation_error", description="Error type")
    message: str = Field(..., description="Overall error message")
    errors: List[ValidationError] = Field(..., description="Individual validation errors")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RateLimitResponse(BaseZorixModel):
    """Response for rate limit exceeded."""
    error_type: str = Field("rate_limit_exceeded", description="Error type")
    message: str = Field(..., description="Rate limit error message")
    retry_after: int = Field(..., description="Seconds to wait before retry")
    limit: int = Field(..., description="Rate limit")
    remaining: int = Field(..., description="Remaining requests")
    reset_time: datetime = Field(..., description="When rate limit resets")


class ServiceUnavailableResponse(BaseZorixModel):
    """Response for service unavailable."""
    error_type: str = Field("service_unavailable", description="Error type")
    message: str = Field(..., description="Service unavailable message")
    retry_after: Optional[int] = Field(None, description="Seconds to wait before retry")
    maintenance_mode: bool = Field(False, description="Whether in maintenance mode")
    estimated_recovery: Optional[datetime] = Field(None, description="Estimated recovery time")