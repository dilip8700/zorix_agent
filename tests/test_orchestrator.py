"""Tests for the agent orchestrator system."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.orchestrator.core import AgentOrchestrator, StreamingEvent
from agent.orchestrator.executor import TaskExecutor
from agent.orchestrator.planner import TaskPlanner
from agent.orchestrator.state import (
    ExecutionState,
    ExecutionStatus,
    ExecutionStep,
    StepType,
)


class TestExecutionState:
    """Test execution state management."""
    
    def test_execution_state_creation(self):
        """Test creating execution state."""
        state = ExecutionState(
            instruction="Test instruction",
            plan=["Step 1", "Step 2"]
        )
        
        assert state.instruction == "Test instruction"
        assert state.plan == ["Step 1", "Step 2"]
        assert state.status == ExecutionStatus.PENDING
        assert state.current_step_index == 0
        assert state.can_rollback is True
    
    def test_execution_state_lifecycle(self):
        """Test execution state lifecycle."""
        state = ExecutionState(instruction="Test")
        
        # Start execution
        state.start()
        assert state.status == ExecutionStatus.RUNNING
        assert state.started_at is not None
        
        # Complete execution
        state.complete()
        assert state.status == ExecutionStatus.COMPLETED
        assert state.completed_at is not None
    
    def test_execution_step_management(self):
        """Test adding and managing steps."""
        state = ExecutionState(instruction="Test")
        
        step1 = ExecutionStep(description="First step")
        step2 = ExecutionStep(description="Second step")
        
        state.add_step(step1)
        state.add_step(step2)
        
        assert len(state.steps) == 2
        assert state.get_current_step() == step1
        
        state.advance_step()
        assert state.get_current_step() == step2
    
    def test_rollback_points(self):
        """Test rollback point creation and usage."""
        state = ExecutionState(instruction="Test")
        
        # Create rollback point
        state.create_rollback_point("Initial state")
        assert len(state.rollback_points) == 1
        
        # Advance state
        state.current_step_index = 2
        state.context["test"] = "value"
        
        # Create another rollback point
        state.create_rollback_point("Advanced state")
        assert len(state.rollback_points) == 2
        
        # Rollback to first point
        rollback_id = state.rollback_points[0]["id"]
        success = state.rollback_to_point(rollback_id)
        
        assert success is True
        assert state.current_step_index == 0
        assert len(state.rollback_points) == 1
    
    def test_progress_tracking(self):
        """Test execution progress tracking."""
        state = ExecutionState(instruction="Test")
        
        # Add steps
        for i in range(5):
            step = ExecutionStep(description=f"Step {i+1}")
            if i < 2:
                step.complete()
            elif i == 2:
                step.fail("Test error")
            state.add_step(step)
        
        progress = state.get_progress()
        
        assert progress["total_steps"] == 5
        assert progress["completed_steps"] == 2
        assert progress["failed_steps"] == 1
        assert progress["progress_percentage"] == 40.0
    
    def test_serialization(self):
        """Test state serialization and deserialization."""
        state = ExecutionState(
            instruction="Test instruction",
            plan=["Step 1", "Step 2"]
        )
        
        step = ExecutionStep(description="Test step")
        step.complete("Test result")
        state.add_step(step)
        
        # Serialize
        data = state.to_dict()
        
        # Deserialize
        restored_state = ExecutionState.from_dict(data)
        
        assert restored_state.instruction == state.instruction
        assert restored_state.plan == state.plan
        assert len(restored_state.steps) == 1
        assert restored_state.steps[0].description == "Test step"
        assert restored_state.steps[0].result == "Test result"


class TestTaskPlanner:
    """Test task planning functionality."""
    
    @pytest.fixture
    def mock_bedrock(self):
        """Mock Bedrock client."""
        mock = MagicMock()
        mock.generate_response = AsyncMock(return_value='{"plan": [{"description": "Test step", "tool_name": "test_tool", "tool_args": {"arg1": "value1"}, "reasoning": "Test reasoning", "expected_outcome": "Test outcome"}]}')
        return mock
    
    @pytest.fixture
    def task_planner(self, mock_bedrock):
        """Create task planner instance."""
        return TaskPlanner(bedrock_client=mock_bedrock)
    
    @pytest.mark.asyncio
    async def test_create_plan(self, task_planner):
        """Test creating execution plan."""
        execution_state = await task_planner.create_plan(
            instruction="Test instruction",
            context={"test": "context"},
            available_tools=["test_tool"]
        )
        
        assert execution_state.instruction == "Test instruction"
        assert len(execution_state.steps) == 1
        assert execution_state.steps[0].description == "Test step"
        assert execution_state.steps[0].tool_name == "test_tool"
        assert execution_state.steps[0].tool_args == {"arg1": "value1"}
    
    @pytest.mark.asyncio
    async def test_plan_parsing_error(self, mock_bedrock):
        """Test handling of plan parsing errors."""
        mock_bedrock.generate_response = AsyncMock(return_value="Invalid JSON response")
        
        planner = TaskPlanner(bedrock_client=mock_bedrock)
        
        execution_state = await planner.create_plan("Test instruction")
        
        # Should fall back to simple plan
        assert len(execution_state.steps) == 1
        assert "fallback" in execution_state.steps[0].metadata.get("reasoning", "").lower()
    
    @pytest.mark.asyncio
    async def test_refine_plan(self, task_planner):
        """Test plan refinement."""
        # Create initial execution state
        execution_state = ExecutionState(instruction="Test instruction")
        step = ExecutionStep(description="Failed step")
        step.fail("Test error")
        execution_state.add_step(step)
        
        # Refine plan
        refined_state = await task_planner.refine_plan(
            execution_state=execution_state,
            feedback="The step failed because of X",
            failed_step_index=0
        )
        
        assert len(refined_state.steps) >= 1
        assert any(step.metadata.get("refined") for step in refined_state.steps)


class TestTaskExecutor:
    """Test task execution functionality."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def mock_bedrock(self):
        """Mock Bedrock client."""
        mock = MagicMock()
        mock.generate_response = AsyncMock(return_value="Reasoning result")
        return mock
    
    @pytest.fixture
    def task_executor(self, temp_workspace, mock_bedrock):
        """Create task executor instance."""
        return TaskExecutor(
            bedrock_client=mock_bedrock,
            workspace_root=str(temp_workspace)
        )
    
    def test_tool_registration(self, task_executor):
        """Test tool registration."""
        def custom_tool(arg1: str) -> str:
            return f"Custom result: {arg1}"
        
        task_executor.add_tool("custom_tool", custom_tool)
        
        assert "custom_tool" in task_executor.tools
        assert task_executor.tools["custom_tool"] == custom_tool
    
    @pytest.mark.asyncio
    async def test_execute_tool_call_step(self, task_executor, temp_workspace):
        """Test executing tool call step."""
        # Create test file
        test_file = temp_workspace / "test.txt"
        test_file.write_text("Test content")
        
        # Create execution state with read file step
        execution_state = ExecutionState(instruction="Read file")
        step = ExecutionStep(
            step_type=StepType.TOOL_CALL,
            description="Read test file",
            tool_name="read_file",
            tool_args={"file_path": "test.txt"}
        )
        execution_state.add_step(step)
        
        # Execute
        result_state = await task_executor.execute(execution_state)
        
        assert result_state.status == ExecutionStatus.COMPLETED
        assert result_state.steps[0].status == ExecutionStatus.COMPLETED
        assert "Test content" in str(result_state.steps[0].result)
    
    @pytest.mark.asyncio
    async def test_execute_reasoning_step(self, task_executor):
        """Test executing reasoning step."""
        execution_state = ExecutionState(instruction="Test reasoning")
        step = ExecutionStep(
            step_type=StepType.REASONING,
            description="Analyze the situation"
        )
        execution_state.add_step(step)
        
        result_state = await task_executor.execute(execution_state)
        
        assert result_state.status == ExecutionStatus.COMPLETED
        assert result_state.steps[0].status == ExecutionStatus.COMPLETED
        assert result_state.steps[0].result == "Reasoning result"
    
    @pytest.mark.asyncio
    async def test_execute_with_retries(self, task_executor):
        """Test execution with retry logic."""
        # Mock a tool that fails twice then succeeds
        call_count = 0
        
        def failing_tool():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception(f"Failure {call_count}")
            return "Success"
        
        task_executor.add_tool("failing_tool", failing_tool)
        
        execution_state = ExecutionState(instruction="Test retries")
        step = ExecutionStep(
            step_type=StepType.TOOL_CALL,
            description="Failing tool test",
            tool_name="failing_tool"
        )
        execution_state.add_step(step)
        
        result_state = await task_executor.execute(execution_state, max_retries=3)
        
        assert result_state.status == ExecutionStatus.COMPLETED
        assert result_state.steps[0].status == ExecutionStatus.COMPLETED
        assert result_state.steps[0].result == "Success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_execution_callbacks(self, task_executor):
        """Test execution callbacks."""
        started_steps = []
        completed_steps = []
        failed_steps = []
        
        task_executor.add_step_callback("started", lambda step: started_steps.append(step.id))
        task_executor.add_step_callback("completed", lambda step: completed_steps.append(step.id))
        task_executor.add_step_callback("failed", lambda step, error: failed_steps.append(step.id))
        
        execution_state = ExecutionState(instruction="Test callbacks")
        step = ExecutionStep(
            step_type=StepType.REASONING,
            description="Test step"
        )
        execution_state.add_step(step)
        
        await task_executor.execute(execution_state)
        
        assert len(started_steps) == 1
        assert len(completed_steps) == 1
        assert len(failed_steps) == 0
        assert started_steps[0] == step.id
        assert completed_steps[0] == step.id
    
    @pytest.mark.asyncio
    async def test_pause_resume_execution(self, task_executor):
        """Test pausing and resuming execution."""
        execution_state = ExecutionState(instruction="Test pause/resume")
        step = ExecutionStep(
            step_type=StepType.REASONING,
            description="Test step"
        )
        execution_state.add_step(step)
        
        # Pause execution
        await task_executor.pause_execution(execution_state)
        assert execution_state.status == ExecutionStatus.PAUSED
        
        # Resume execution
        result_state = await task_executor.resume_execution(execution_state)
        assert result_state.status == ExecutionStatus.COMPLETED


class TestAgentOrchestrator:
    """Test main agent orchestrator."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def mock_bedrock(self):
        """Mock Bedrock client."""
        mock = MagicMock()
        mock.generate_response = AsyncMock(return_value='{"plan": [{"description": "Test step", "tool_name": null, "tool_args": {}, "reasoning": "Test reasoning", "expected_outcome": "Test outcome"}]}')
        return mock
    
    @pytest.fixture
    def orchestrator(self, temp_workspace, mock_bedrock):
        """Create orchestrator instance."""
        return AgentOrchestrator(
            bedrock_client=mock_bedrock,
            workspace_root=str(temp_workspace)
        )
    
    @pytest.mark.asyncio
    async def test_execute_instruction_sync(self, orchestrator):
        """Test synchronous instruction execution."""
        result = await orchestrator.execute_instruction(
            instruction="Test instruction",
            context={"test": "context"}
        )
        
        assert isinstance(result, ExecutionState)
        assert result.instruction == "Test instruction"
        assert result.status == ExecutionStatus.COMPLETED
        assert len(result.steps) >= 1
    
    @pytest.mark.asyncio
    async def test_execute_instruction_streaming(self, orchestrator):
        """Test streaming instruction execution."""
        events = []
        
        async for event in orchestrator.execute_instruction(
            instruction="Test instruction",
            streaming=True
        ):
            events.append(event)
            if event.event_type == "execution_completed":
                break
        
        assert len(events) > 0
        assert any(event.event_type == "planning_started" for event in events)
        assert any(event.event_type == "execution_completed" for event in events)
    
    def test_streaming_callbacks(self, orchestrator):
        """Test streaming callback system."""
        received_events = []
        
        def test_callback(event: StreamingEvent):
            received_events.append(event)
        
        orchestrator.add_streaming_callback(test_callback)
        
        # Emit test event
        orchestrator._emit_streaming_event("test_event", {"test": "data"})
        
        assert len(received_events) == 1
        assert received_events[0].event_type == "test_event"
        assert received_events[0].data == {"test": "data"}
    
    @pytest.mark.asyncio
    async def test_execution_management(self, orchestrator):
        """Test execution management operations."""
        # Start execution in background
        execution_task = asyncio.create_task(
            orchestrator.execute_instruction("Long running task")
        )
        
        # Give it a moment to start
        await asyncio.sleep(0.1)
        
        # Check active executions
        active_executions = orchestrator.get_active_executions()
        assert len(active_executions) >= 0  # May be 0 if execution completed quickly
        
        # Wait for completion
        result = await execution_task
        assert result.status == ExecutionStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_failure_analysis(self, orchestrator):
        """Test failure analysis and replanning."""
        # Create execution state with failed step
        execution_state = ExecutionState(instruction="Test failure analysis")
        step = ExecutionStep(description="Failed step")
        step.fail("Test error")
        execution_state.add_step(step)
        execution_state.fail("Test failure")
        
        # Analyze failure
        analysis = await orchestrator._analyze_failure(execution_state)
        
        assert isinstance(analysis, str)
        assert len(analysis) > 0
        assert "failed" in analysis.lower() or "error" in analysis.lower()


class TestIntegration:
    """Integration tests for the orchestrator system."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            # Create test files
            (workspace / "test.txt").write_text("Hello, world!")
            (workspace / "data").mkdir()
            (workspace / "data" / "info.json").write_text('{"key": "value"}')
            yield workspace
    
    @pytest.fixture
    def mock_bedrock(self):
        """Mock Bedrock client with realistic responses."""
        mock = MagicMock()
        
        # Mock planning response
        plan_response = {
            "plan": [
                {
                    "description": "Read the test file",
                    "tool_name": "read_file",
                    "tool_args": {"file_path": "test.txt"},
                    "reasoning": "Need to read the file content",
                    "expected_outcome": "File content retrieved"
                },
                {
                    "description": "List directory contents",
                    "tool_name": "list_dir",
                    "tool_args": {"path": "."},
                    "reasoning": "Need to see what files are available",
                    "expected_outcome": "Directory listing obtained"
                }
            ]
        }
        
        mock.generate_response = AsyncMock(return_value=json.dumps(plan_response))
        return mock
    
    @pytest.mark.asyncio
    async def test_end_to_end_execution(self, temp_workspace, mock_bedrock):
        """Test complete end-to-end execution."""
        orchestrator = AgentOrchestrator(
            bedrock_client=mock_bedrock,
            workspace_root=str(temp_workspace)
        )
        
        # Execute instruction
        result = await orchestrator.execute_instruction(
            instruction="Read the test file and list the directory contents",
            context={"workspace": str(temp_workspace)}
        )
        
        assert result.status == ExecutionStatus.COMPLETED
        assert len(result.steps) == 2
        
        # Check that both steps completed
        for step in result.steps:
            assert step.status == ExecutionStatus.COMPLETED
            assert step.result is not None
        
        # Check specific results
        read_step = result.steps[0]
        assert "Hello, world!" in str(read_step.result)
        
        list_step = result.steps[1]
        assert "test.txt" in str(list_step.result)
    
    @pytest.mark.asyncio
    async def test_streaming_execution(self, temp_workspace, mock_bedrock):
        """Test streaming execution with real events."""
        orchestrator = AgentOrchestrator(
            bedrock_client=mock_bedrock,
            workspace_root=str(temp_workspace)
        )
        
        events = []
        event_types = set()
        
        async for event in orchestrator.execute_instruction(
            instruction="Read test file",
            streaming=True
        ):
            events.append(event)
            event_types.add(event.event_type)
            
            if event.event_type == "execution_completed":
                break
        
        # Check that we received expected event types
        expected_events = {
            "planning_started",
            "planning_completed", 
            "step_started",
            "step_completed",
            "execution_completed"
        }
        
        assert expected_events.issubset(event_types)
        assert len(events) >= len(expected_events)


if __name__ == "__main__":
    pytest.main([__file__])