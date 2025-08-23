"""Plan and execution models for Zorix Agent."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field, validator

from agent.models.base import BaseZorixModel, CostEstimate, StepType, TaskMode, TaskStatus


class PlanStep(BaseZorixModel):
    """A single step in an execution plan."""
    id: str = Field(..., description="Unique step identifier")
    step_type: StepType = Field(..., description="Type of step")
    tool: Optional[str] = Field(None, description="Tool to execute (if tool_call)")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    rationale: str = Field(..., description="Reasoning for this step")
    requires_approval: bool = Field(False, description="Whether step requires user approval")
    dependencies: List[str] = Field(default_factory=list, description="IDs of steps this depends on")
    estimated_duration_ms: Optional[int] = Field(None, description="Estimated execution time")
    
    @validator('rationale')
    def rationale_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Step rationale cannot be empty')
        return v.strip()


class PlanPreview(BaseZorixModel):
    """Preview of changes that will be made by a plan."""
    files_to_create: List[str] = Field(default_factory=list, description="Files to be created")
    files_to_modify: List[str] = Field(default_factory=list, description="Files to be modified")
    files_to_delete: List[str] = Field(default_factory=list, description="Files to be deleted")
    commands_to_run: List[str] = Field(default_factory=list, description="Commands to execute")
    git_operations: List[str] = Field(default_factory=list, description="Git operations")
    summary: str = Field(..., description="High-level summary of changes")
    risk_level: str = Field("low", description="Risk level: low, medium, high")
    
    @validator('risk_level')
    def validate_risk_level(cls, v):
        if v not in ["low", "medium", "high"]:
            raise ValueError('Risk level must be low, medium, or high')
        return v


class Plan(BaseZorixModel):
    """A complete execution plan for a task."""
    id: str = Field(..., description="Unique plan identifier")
    instruction: str = Field(..., description="Original user instruction")
    mode: TaskMode = Field(..., description="Task execution mode")
    steps: List[PlanStep] = Field(..., description="Ordered list of execution steps")
    cost_estimate: CostEstimate = Field(..., description="Estimated cost and resources")
    preview: PlanPreview = Field(..., description="Preview of changes")
    requires_approval: bool = Field(..., description="Whether plan requires approval")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('steps')
    def steps_not_empty(cls, v):
        if not v:
            raise ValueError('Plan must have at least one step')
        return v
    
    @validator('requires_approval', always=True)
    def calculate_requires_approval(cls, v, values):
        if 'steps' in values:
            return any(step.requires_approval for step in values['steps'])
        return v


class StepExecution(BaseZorixModel):
    """Execution result for a single plan step."""
    step_id: str = Field(..., description="ID of the executed step")
    status: TaskStatus = Field(..., description="Execution status")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(None, description="When step completed")
    result: Any = Field(None, description="Step execution result")
    error: Optional[str] = Field(None, description="Error message if failed")
    duration_ms: Optional[int] = Field(None, description="Actual execution duration")
    logs: List[str] = Field(default_factory=list, description="Execution logs")
    
    @validator('completed_at')
    def completed_after_started(cls, v, values):
        if v and 'started_at' in values and v < values['started_at']:
            raise ValueError('completed_at must be after started_at')
        return v


class ExecutionResult(BaseZorixModel):
    """Complete result of plan execution."""
    plan_id: str = Field(..., description="ID of the executed plan")
    status: TaskStatus = Field(..., description="Overall execution status")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(None, description="When execution completed")
    step_executions: List[StepExecution] = Field(default_factory=list, description="Individual step results")
    applied_changes: List[Any] = Field(default_factory=list, description="Changes that were applied")
    command_results: List[Any] = Field(default_factory=list, description="Command execution results")
    git_operations: List[Any] = Field(default_factory=list, description="Git operations performed")
    errors: List[str] = Field(default_factory=list, description="Errors encountered")
    logs_token: Optional[str] = Field(None, description="Token for accessing detailed logs")
    total_duration_ms: Optional[int] = Field(None, description="Total execution time")
    
    @property
    def success(self) -> bool:
        """Whether execution was successful."""
        return self.status == TaskStatus.COMPLETED
    
    @property
    def failed_steps(self) -> List[StepExecution]:
        """Get list of failed step executions."""
        return [step for step in self.step_executions if step.status == TaskStatus.FAILED]
    
    @property
    def completed_steps(self) -> List[StepExecution]:
        """Get list of completed step executions."""
        return [step for step in self.step_executions if step.status == TaskStatus.COMPLETED]


class Budget(BaseZorixModel):
    """Resource budget for task execution."""
    max_steps: Optional[int] = Field(None, ge=1, description="Maximum number of steps")
    max_tokens: Optional[int] = Field(None, ge=1, description="Maximum token usage")
    max_duration_ms: Optional[int] = Field(None, ge=1, description="Maximum execution time")
    max_cost_usd: Optional[float] = Field(None, ge=0, description="Maximum cost in USD")


class TaskRequest(BaseZorixModel):
    """Request to plan or execute a task."""
    message: str = Field(..., description="Task instruction or description")
    mode: TaskMode = Field(TaskMode.EDIT, description="Task execution mode")
    budget: Optional[Budget] = Field(None, description="Resource constraints")
    auto_apply: bool = Field(False, description="Whether to auto-apply without approval")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    
    @validator('message')
    def message_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Task message cannot be empty')
        return v.strip()


class ApplyRequest(BaseZorixModel):
    """Request to apply a plan."""
    plan_id: str = Field(..., description="ID of plan to apply")
    approve_all: bool = Field(False, description="Approve all steps requiring approval")
    approved_steps: List[str] = Field(default_factory=list, description="Specific steps to approve")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")


class ChatRequest(BaseZorixModel):
    """Request for streaming chat interaction."""
    messages: List[Any] = Field(..., description="Conversation messages")
    tools_allow: Optional[List[str]] = Field(None, description="Allowed tools for this chat")
    mode: TaskMode = Field(TaskMode.EXPLAIN, description="Chat mode")
    stream: bool = Field(True, description="Whether to stream responses")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    
    @validator('messages')
    def messages_not_empty(cls, v):
        if not v:
            raise ValueError('Messages list cannot be empty')
        return v


class ChatEvent(BaseZorixModel):
    """Event in a streaming chat response."""
    event_type: str = Field(..., description="Type of event")
    data: Any = Field(None, description="Event data")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('event_type')
    def event_type_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Event type cannot be empty')
        return v.strip()