"""Tests for data models and schemas."""

from datetime import datetime, timedelta
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from agent.models.api import (
    ApplyResponse,
    GitCommitRequest,
    GitStatusResponse,
    IndexRebuildResponse,
    PlanResponse,
    SearchRequest,
    SearchResponse,
)
from agent.models.base import (
    CommandResult,
    CostEstimate,
    ErrorResponse,
    ErrorType,
    FileChange,
    HealthStatus,
    Message,
    MessageRole,
    PaginatedResponse,
    PaginationParams,
    SearchResult,
    ToolCall,
    ToolResult,
)
from agent.models.plan import (
    ApplyRequest,
    Budget,
    ChatRequest,
    ExecutionResult,
    Plan,
    PlanPreview,
    PlanStep,
    StepExecution,
    StepType,
    TaskMode,
    TaskRequest,
    TaskStatus,
)


class TestBaseModels:
    """Test cases for base models."""
    
    def test_message_creation(self):
        """Test Message model creation and validation."""
        message = Message(role=MessageRole.USER, content="Hello, world!")
        
        assert message.role == MessageRole.USER
        assert message.content == "Hello, world!"
        assert isinstance(message.timestamp, datetime)
        assert message.metadata == {}
    
    def test_message_empty_content(self):
        """Test Message validation with empty content."""
        with pytest.raises(ValidationError, match="Message content cannot be empty"):
            Message(role=MessageRole.USER, content="")
        
        with pytest.raises(ValidationError, match="Message content cannot be empty"):
            Message(role=MessageRole.USER, content="   ")
    
    def test_tool_call_creation(self):
        """Test ToolCall model creation."""
        tool_call = ToolCall(
            id="call_123",
            name="read_file",
            arguments={"path": "test.py"}
        )
        
        assert tool_call.id == "call_123"
        assert tool_call.name == "read_file"
        assert tool_call.arguments == {"path": "test.py"}
    
    def test_tool_result_creation(self):
        """Test ToolResult model creation."""
        result = ToolResult(
            tool_call_id="call_123",
            success=True,
            result={"content": "print('hello')"},
            duration_ms=150
        )
        
        assert result.tool_call_id == "call_123"
        assert result.success is True
        assert result.result == {"content": "print('hello')"}
        assert result.duration_ms == 150
        assert result.error is None
    
    def test_cost_estimate_creation(self):
        """Test CostEstimate model creation."""
        cost = CostEstimate(
            estimated_tokens=1000,
            estimated_cost_usd=0.05,
            confidence=0.8,
            breakdown={"input_tokens": 500, "output_tokens": 500}
        )
        
        assert cost.estimated_tokens == 1000
        assert cost.estimated_cost_usd == 0.05
        assert cost.confidence == 0.8
        assert cost.breakdown["input_tokens"] == 500
    
    def test_cost_estimate_validation(self):
        """Test CostEstimate validation."""
        with pytest.raises(ValidationError):
            CostEstimate(estimated_tokens=-1, estimated_cost_usd=0.05, confidence=0.8)
        
        with pytest.raises(ValidationError):
            CostEstimate(estimated_tokens=1000, estimated_cost_usd=-0.05, confidence=0.8)
        
        with pytest.raises(ValidationError):
            CostEstimate(estimated_tokens=1000, estimated_cost_usd=0.05, confidence=1.5)
    
    def test_search_result_creation(self):
        """Test SearchResult model creation."""
        result = SearchResult(
            path="src/main.py",
            start_line=10,
            end_line=15,
            snippet="def main():\n    print('hello')",
            score=0.95
        )
        
        assert result.path == "src/main.py"
        assert result.start_line == 10
        assert result.end_line == 15
        assert result.score == 0.95
    
    def test_search_result_validation(self):
        """Test SearchResult validation."""
        with pytest.raises(ValidationError, match="end_line must be >= start_line"):
            SearchResult(
                path="test.py",
                start_line=15,
                end_line=10,
                snippet="code",
                score=0.5
            )
    
    def test_pagination_params(self):
        """Test PaginationParams model."""
        params = PaginationParams(page=2, page_size=10)
        
        assert params.page == 2
        assert params.page_size == 10
        assert params.offset == 10  # (2-1) * 10
    
    def test_paginated_response(self):
        """Test PaginatedResponse model."""
        response = PaginatedResponse(
            items=["item1", "item2", "item3"],
            total=25,
            page=2,
            page_size=10
        )
        
        assert len(response.items) == 3
        assert response.total == 25
        assert response.page == 2
        assert response.page_size == 10
        assert response.total_pages == 3  # ceil(25/10)
        assert response.has_next is True  # page 2 < 3 pages
        assert response.has_prev is True  # page 2 > 1


class TestPlanModels:
    """Test cases for plan models."""
    
    def test_plan_step_creation(self):
        """Test PlanStep model creation."""
        step = PlanStep(
            id="step_1",
            step_type=StepType.TOOL_CALL,
            tool="read_file",
            arguments={"path": "test.py"},
            rationale="Need to read the file to understand its structure",
            requires_approval=False
        )
        
        assert step.id == "step_1"
        assert step.step_type == StepType.TOOL_CALL
        assert step.tool == "read_file"
        assert step.requires_approval is False
    
    def test_plan_step_validation(self):
        """Test PlanStep validation."""
        with pytest.raises(ValidationError, match="Step rationale cannot be empty"):
            PlanStep(
                id="step_1",
                step_type=StepType.TOOL_CALL,
                rationale=""
            )
    
    def test_plan_preview_creation(self):
        """Test PlanPreview model creation."""
        preview = PlanPreview(
            files_to_create=["new_file.py"],
            files_to_modify=["existing.py"],
            commands_to_run=["python test.py"],
            summary="Add new functionality and update existing code",
            risk_level="medium"
        )
        
        assert preview.files_to_create == ["new_file.py"]
        assert preview.files_to_modify == ["existing.py"]
        assert preview.risk_level == "medium"
    
    def test_plan_preview_validation(self):
        """Test PlanPreview validation."""
        with pytest.raises(ValidationError, match="Risk level must be low, medium, or high"):
            PlanPreview(
                summary="Test summary",
                risk_level="extreme"
            )
    
    def test_plan_creation(self):
        """Test Plan model creation."""
        steps = [
            PlanStep(
                id="step_1",
                step_type=StepType.TOOL_CALL,
                rationale="First step"
            )
        ]
        
        cost_estimate = CostEstimate(
            estimated_tokens=500,
            estimated_cost_usd=0.025,
            confidence=0.9
        )
        
        preview = PlanPreview(
            summary="Test plan",
            risk_level="low"
        )
        
        plan = Plan(
            id="plan_123",
            instruction="Create a test file",
            mode=TaskMode.CREATE,
            steps=steps,
            cost_estimate=cost_estimate,
            preview=preview,
            requires_approval=False
        )
        
        assert plan.id == "plan_123"
        assert plan.mode == TaskMode.CREATE
        assert len(plan.steps) == 1
        assert plan.requires_approval is False
    
    def test_plan_validation(self):
        """Test Plan validation."""
        cost_estimate = CostEstimate(
            estimated_tokens=500,
            estimated_cost_usd=0.025,
            confidence=0.9
        )
        
        preview = PlanPreview(
            summary="Test plan",
            risk_level="low"
        )
        
        with pytest.raises(ValidationError, match="Plan must have at least one step"):
            Plan(
                id="plan_123",
                instruction="Test",
                mode=TaskMode.CREATE,
                steps=[],
                cost_estimate=cost_estimate,
                preview=preview,
                requires_approval=False
            )
    
    def test_execution_result_properties(self):
        """Test ExecutionResult computed properties."""
        step_executions = [
            StepExecution(
                step_id="step_1",
                status=TaskStatus.COMPLETED,
                result="success"
            ),
            StepExecution(
                step_id="step_2",
                status=TaskStatus.FAILED,
                error="Something went wrong"
            )
        ]
        
        result = ExecutionResult(
            plan_id="plan_123",
            status=TaskStatus.COMPLETED,
            step_executions=step_executions
        )
        
        assert result.success is True  # Overall status is COMPLETED
        assert len(result.failed_steps) == 1
        assert len(result.completed_steps) == 1
        assert result.failed_steps[0].step_id == "step_2"
        assert result.completed_steps[0].step_id == "step_1"
    
    def test_task_request_validation(self):
        """Test TaskRequest validation."""
        with pytest.raises(ValidationError, match="Task message cannot be empty"):
            TaskRequest(message="")
        
        with pytest.raises(ValidationError, match="Task message cannot be empty"):
            TaskRequest(message="   ")
    
    def test_chat_request_validation(self):
        """Test ChatRequest validation."""
        with pytest.raises(ValidationError, match="Messages list cannot be empty"):
            ChatRequest(messages=[])


class TestAPIModels:
    """Test cases for API models."""
    
    def test_search_request_validation(self):
        """Test SearchRequest validation."""
        # Valid request
        request = SearchRequest(query="test function", top_k=10)
        assert request.query == "test function"
        assert request.top_k == 10
        
        # Invalid empty query
        with pytest.raises(ValidationError, match="Search query cannot be empty"):
            SearchRequest(query="")
    
    def test_search_response_creation(self):
        """Test SearchResponse model creation."""
        results = [
            SearchResult(
                path="test.py",
                start_line=1,
                end_line=5,
                snippet="def test():",
                score=0.9
            )
        ]
        
        response = SearchResponse(
            results=results,
            total_found=1,
            query="test function",
            duration_ms=150
        )
        
        assert len(response.results) == 1
        assert response.total_found == 1
        assert response.query == "test function"
        assert response.duration_ms == 150
    
    def test_git_commit_request_validation(self):
        """Test GitCommitRequest validation."""
        # Valid request
        request = GitCommitRequest(message="Add new feature")
        assert request.message == "Add new feature"
        assert request.add_all is True
        
        # Invalid empty message
        with pytest.raises(ValidationError, match="Commit message cannot be empty"):
            GitCommitRequest(message="")
    
    def test_git_status_response_creation(self):
        """Test GitStatusResponse model creation."""
        response = GitStatusResponse(
            modified=["file1.py", "file2.py"],
            added=["new_file.py"],
            deleted=[],
            untracked=["temp.txt"],
            ignored=[],
            branch="main",
            is_clean=False
        )
        
        assert len(response.modified) == 2
        assert len(response.added) == 1
        assert response.branch == "main"
        assert response.is_clean is False
    
    def test_index_rebuild_response_creation(self):
        """Test IndexRebuildResponse model creation."""
        response = IndexRebuildResponse(
            success=True,
            stats={"files": 100, "chunks": 500},
            duration_ms=5000,
            files_processed=100,
            chunks_created=500,
            errors=[]
        )
        
        assert response.success is True
        assert response.stats["files"] == 100
        assert response.files_processed == 100
        assert len(response.errors) == 0


class TestModelIntegration:
    """Integration tests for model interactions."""
    
    def test_complete_plan_workflow(self):
        """Test complete plan creation and execution workflow."""
        # Create a plan
        steps = [
            PlanStep(
                id="step_1",
                step_type=StepType.TOOL_CALL,
                tool="read_file",
                arguments={"path": "test.py"},
                rationale="Read the file to understand structure"
            ),
            PlanStep(
                id="step_2",
                step_type=StepType.TOOL_CALL,
                tool="write_file",
                arguments={"path": "new_test.py", "content": "# New file"},
                rationale="Create new file based on analysis"
            )
        ]
        
        cost_estimate = CostEstimate(
            estimated_tokens=1000,
            estimated_cost_usd=0.05,
            confidence=0.85
        )
        
        preview = PlanPreview(
            files_to_create=["new_test.py"],
            files_to_modify=[],
            summary="Create new test file based on existing structure",
            risk_level="low"
        )
        
        plan = Plan(
            id="plan_123",
            instruction="Create a new test file",
            mode=TaskMode.CREATE,
            steps=steps,
            cost_estimate=cost_estimate,
            preview=preview,
            requires_approval=False
        )
        
        # Validate plan structure
        assert len(plan.steps) == 2
        assert plan.steps[0].tool == "read_file"
        assert plan.steps[1].tool == "write_file"
        assert plan.requires_approval is False
        
        # Create execution results
        step_executions = [
            StepExecution(
                step_id="step_1",
                status=TaskStatus.COMPLETED,
                result={"content": "existing file content"},
                duration_ms=100
            ),
            StepExecution(
                step_id="step_2",
                status=TaskStatus.COMPLETED,
                result={"success": True},
                duration_ms=50
            )
        ]
        
        execution_result = ExecutionResult(
            plan_id="plan_123",
            status=TaskStatus.COMPLETED,
            step_executions=step_executions,
            total_duration_ms=150
        )
        
        # Validate execution
        assert execution_result.success is True
        assert len(execution_result.completed_steps) == 2
        assert len(execution_result.failed_steps) == 0
        assert execution_result.total_duration_ms == 150
    
    def test_error_handling_models(self):
        """Test error handling with models."""
        # Create error response
        error = ErrorResponse(
            error_type=ErrorType.VALIDATION_ERROR,
            message="Invalid input provided",
            details={"field": "query", "value": ""},
            suggestion="Provide a non-empty query string"
        )
        
        assert error.error_type == ErrorType.VALIDATION_ERROR
        assert error.message == "Invalid input provided"
        assert error.details["field"] == "query"
        assert error.suggestion is not None
        
        # Test failed execution
        failed_execution = ExecutionResult(
            plan_id="plan_456",
            status=TaskStatus.FAILED,
            step_executions=[
                StepExecution(
                    step_id="step_1",
                    status=TaskStatus.FAILED,
                    error="File not found"
                )
            ],
            errors=["File not found: test.py"]
        )
        
        assert failed_execution.success is False
        assert len(failed_execution.failed_steps) == 1
        assert len(failed_execution.errors) == 1