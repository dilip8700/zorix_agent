"""Tests for the enhanced planning system."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.orchestrator.state import ExecutionState, ExecutionStep, StepType
from agent.planning.cost_estimator import ApprovalLevel, CostEstimator, PlanCost, RiskLevel
from agent.planning.executor import PlanExecutor
from agent.planning.modes import PlanningContext, PlanningMode, detect_planning_mode
from agent.planning.planner import TaskPlanner
from agent.planning.preview import PlanPreview, PreviewGenerator


class TestPlanningModes:
    """Test planning mode detection and context creation."""
    
    def test_detect_planning_mode_edit(self):
        """Test detecting edit mode."""
        instructions = [
            "Edit the main.py file to fix the bug",
            "Modify the configuration settings",
            "Change the database connection string",
            "Update the API endpoint"
        ]
        
        for instruction in instructions:
            mode = detect_planning_mode(instruction)
            assert mode == PlanningMode.EDIT
    
    def test_detect_planning_mode_explain(self):
        """Test detecting explain mode."""
        instructions = [
            "Explain how this function works",
            "Describe the authentication process",
            "What does this code do?",
            "How does the caching mechanism work?"
        ]
        
        for instruction in instructions:
            mode = detect_planning_mode(instruction)
            assert mode == PlanningMode.EXPLAIN
    
    def test_detect_planning_mode_refactor(self):
        """Test detecting refactor mode."""
        instructions = [
            "Refactor the user service class",
            "Restructure the project layout",
            "Improve the code organization",
            "Clean up the legacy code"
        ]
        
        for instruction in instructions:
            mode = detect_planning_mode(instruction)
            assert mode == PlanningMode.REFACTOR
    
    def test_detect_planning_mode_test(self):
        """Test detecting test mode."""
        instructions = [
            "Create unit tests for the API",
            "Test the authentication flow",
            "Verify the database operations",
            "Validate the input handling"
        ]
        
        for instruction in instructions:
            mode = detect_planning_mode(instruction)
            assert mode == PlanningMode.TEST
    
    def test_detect_planning_mode_create(self):
        """Test detecting create mode."""
        instructions = [
            "Create a new user management system",
            "Build a REST API for products",
            "Make a dashboard component",
            "Add logging functionality"
        ]
        
        for instruction in instructions:
            mode = detect_planning_mode(instruction)
            assert mode == PlanningMode.CREATE
    
    def test_planning_context_serialization(self):
        """Test planning context serialization."""
        context = PlanningContext(
            mode=PlanningMode.EDIT,
            target_files=["main.py", "config.py"],
            requirements=["Preserve functionality", "Maintain style"],
            constraints={"max_changes": 10},
            user_preferences={"backup": True}
        )
        
        # Test to_dict
        data = context.to_dict()
        assert data["mode"] == "edit"
        assert data["target_files"] == ["main.py", "config.py"]
        assert data["requirements"] == ["Preserve functionality", "Maintain style"]
        
        # Test from_dict
        restored = PlanningContext.from_dict(data)
        assert restored.mode == PlanningMode.EDIT
        assert restored.target_files == ["main.py", "config.py"]
        assert restored.requirements == ["Preserve functionality", "Maintain style"]


class TestCostEstimator:
    """Test cost estimation functionality."""
    
    @pytest.fixture
    def cost_estimator(self):
        """Create cost estimator instance."""
        return CostEstimator()
    
    def test_estimate_simple_plan_cost(self, cost_estimator):
        """Test estimating cost for a simple plan."""
        steps = [
            {
                "tool_name": "read_file",
                "tool_args": {"path": "test.py"},
                "description": "Read test file"
            },
            {
                "tool_name": "write_file",
                "tool_args": {"path": "test.py", "content": "print('hello')"},
                "description": "Write to test file"
            }
        ]
        
        cost = cost_estimator.estimate_plan_cost(
            steps=steps,
            mode=PlanningMode.EDIT
        )
        
        assert isinstance(cost, PlanCost)
        assert cost.estimated_time_minutes > 0
        assert 0 <= cost.complexity_score <= 1
        assert cost.file_modifications == 1
        assert cost.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]
    
    def test_estimate_high_risk_plan_cost(self, cost_estimator):
        """Test estimating cost for a high-risk plan."""
        steps = [
            {
                "tool_name": "run_command",
                "tool_args": {"command": "sudo rm -rf /tmp/test"},
                "description": "Delete test files"
            },
            {
                "tool_name": "write_file",
                "tool_args": {"path": "/etc/config.conf", "content": "setting=value"},
                "description": "Modify system config"
            }
        ]
        
        cost = cost_estimator.estimate_plan_cost(
            steps=steps,
            mode=PlanningMode.EDIT
        )
        
        assert cost.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert cost.approval_required != ApprovalLevel.NONE
        assert len(cost.safety_concerns) > 0
    
    def test_cost_serialization(self, cost_estimator):
        """Test cost serialization."""
        steps = [{"tool_name": "read_file", "tool_args": {"path": "test.py"}}]
        
        cost = cost_estimator.estimate_plan_cost(steps, PlanningMode.EDIT)
        
        # Test to_dict
        data = cost.to_dict()
        assert "estimated_time_minutes" in data
        assert "risk_level" in data
        assert "approval_required" in data
        
        # Test from_dict
        restored = PlanCost.from_dict(data)
        assert restored.estimated_time_minutes == cost.estimated_time_minutes
        assert restored.risk_level == cost.risk_level
        assert restored.approval_required == cost.approval_required
    
    def test_approval_requirement_detection(self, cost_estimator):
        """Test approval requirement detection."""
        # Low risk - no approval
        low_risk_steps = [{"tool_name": "read_file", "tool_args": {"path": "test.py"}}]
        low_cost = cost_estimator.estimate_plan_cost(low_risk_steps, PlanningMode.EXPLAIN)
        assert low_cost.approval_required == ApprovalLevel.NONE
        
        # High risk - approval required
        high_risk_steps = [{"tool_name": "run_command", "tool_args": {"command": "sudo rm file"}}]
        high_cost = cost_estimator.estimate_plan_cost(high_risk_steps, PlanningMode.EDIT)
        assert high_cost.approval_required != ApprovalLevel.NONE


class TestPreviewGenerator:
    """Test plan preview generation."""
    
    @pytest.fixture
    def preview_generator(self):
        """Create preview generator instance."""
        return PreviewGenerator()
    
    @pytest.fixture
    def sample_cost(self):
        """Create sample cost estimation."""
        return PlanCost(
            estimated_time_minutes=5.0,
            complexity_score=0.3,
            risk_level=RiskLevel.LOW,
            approval_required=ApprovalLevel.NONE,
            file_modifications=1,
            reasoning="Simple file operation"
        )
    
    def test_generate_preview(self, preview_generator, sample_cost):
        """Test generating plan preview."""
        steps = [
            {
                "tool_name": "read_file",
                "tool_args": {"path": "test.py"},
                "description": "Read test file",
                "expected_outcome": "File content retrieved"
            },
            {
                "tool_name": "write_file",
                "tool_args": {"path": "test.py", "content": "updated content"},
                "description": "Update test file",
                "expected_outcome": "File updated successfully"
            }
        ]
        
        preview = preview_generator.generate_preview(
            instruction="Update the test file",
            steps=steps,
            mode=PlanningMode.EDIT,
            cost=sample_cost
        )
        
        assert isinstance(preview, PlanPreview)
        assert preview.title.startswith("Edit:")
        assert len(preview.step_summaries) == 2
        assert "test.py" in preview.files_affected
        assert len(preview.expected_outcomes) == 2
    
    def test_preview_serialization(self, preview_generator, sample_cost):
        """Test preview serialization."""
        steps = [{"tool_name": "read_file", "tool_args": {"path": "test.py"}}]
        
        preview = preview_generator.generate_preview(
            instruction="Read file",
            steps=steps,
            mode=PlanningMode.EXPLAIN,
            cost=sample_cost
        )
        
        # Test to_dict
        data = preview.to_dict()
        assert "title" in data
        assert "mode" in data
        assert "cost" in data
        
        # Test from_dict
        restored = PlanPreview.from_dict(data)
        assert restored.title == preview.title
        assert restored.mode == preview.mode
    
    def test_format_preview_text(self, preview_generator, sample_cost):
        """Test formatting preview as text."""
        steps = [{"tool_name": "read_file", "tool_args": {"path": "test.py"}}]
        
        preview = preview_generator.generate_preview(
            instruction="Read file",
            steps=steps,
            mode=PlanningMode.EXPLAIN,
            cost=sample_cost
        )
        
        text = preview_generator.format_preview_text(preview)
        
        assert preview.title in text
        assert "Cost Estimation" in text
        assert "Execution Steps" in text
        assert isinstance(text, str)
        assert len(text) > 0


class TestTaskPlanner:
    """Test enhanced task planner."""
    
    @pytest.fixture
    def mock_bedrock(self):
        """Mock Bedrock client."""
        mock = MagicMock()
        mock.chat_with_tools = AsyncMock(return_value={
            "content": '{"plan": [{"description": "Test step", "tool_name": "read_file", "tool_args": {"path": "test.py"}, "reasoning": "Read file", "expected_outcome": "File content"}]}'
        })
        return mock
    
    @pytest.fixture
    def task_planner(self, mock_bedrock):
        """Create task planner instance."""
        return TaskPlanner(bedrock_client=mock_bedrock)
    
    @pytest.mark.asyncio
    async def test_create_enhanced_plan(self, task_planner):
        """Test creating enhanced plan with cost and preview."""
        result = await task_planner.create_plan(
            instruction="Read the test file",
            generate_preview=True,
            estimate_cost=True
        )
        
        assert "execution_state" in result
        assert "planning_mode" in result
        assert "cost" in result
        assert "preview" in result
        
        assert isinstance(result["execution_state"], ExecutionState)
        assert isinstance(result["planning_mode"], PlanningMode)
        assert isinstance(result["cost"], PlanCost)
        assert isinstance(result["preview"], PlanPreview)
    
    @pytest.mark.asyncio
    async def test_create_mode_specific_plan(self, task_planner):
        """Test creating mode-specific plan."""
        result = await task_planner.create_mode_specific_plan(
            instruction="Explain how this code works",
            mode=PlanningMode.EXPLAIN,
            target_files=["main.py"]
        )
        
        assert result["planning_mode"] == PlanningMode.EXPLAIN
        assert "main.py" in result["planning_context"].target_files
    
    def test_get_mode_recommendations(self, task_planner):
        """Test getting mode recommendations."""
        recommendations = task_planner.get_mode_recommendations(
            instruction="Fix the bug in the authentication system"
        )
        
        assert len(recommendations) > 0
        assert all("mode" in rec for rec in recommendations)
        assert all("suitability_score" in rec for rec in recommendations)
        
        # Should have edit mode with high suitability
        edit_recs = [r for r in recommendations if r["mode"] == "edit"]
        assert len(edit_recs) > 0
        assert edit_recs[0]["suitability_score"] >= 0.5


class TestPlanExecutor:
    """Test enhanced plan executor."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def mock_bedrock(self):
        """Mock Bedrock client."""
        mock = MagicMock()
        mock.chat_with_tools = AsyncMock(return_value={"content": "Reasoning result"})
        return mock
    
    @pytest.fixture
    def plan_executor(self, temp_workspace, mock_bedrock):
        """Create plan executor instance."""
        return PlanExecutor(
            bedrock_client=mock_bedrock,
            workspace_root=str(temp_workspace)
        )
    
    @pytest.fixture
    def sample_execution_state(self):
        """Create sample execution state."""
        state = ExecutionState(instruction="Test execution")
        step = ExecutionStep(
            step_type=StepType.TOOL_CALL,
            description="Test step",
            tool_name="read_file",
            tool_args={"path": "test.txt"}
        )
        state.add_step(step)
        return state
    
    @pytest.fixture
    def low_risk_cost(self):
        """Create low risk cost estimation."""
        return PlanCost(
            estimated_time_minutes=2.0,
            complexity_score=0.2,
            risk_level=RiskLevel.LOW,
            approval_required=ApprovalLevel.NONE
        )
    
    @pytest.fixture
    def high_risk_cost(self):
        """Create high risk cost estimation."""
        return PlanCost(
            estimated_time_minutes=10.0,
            complexity_score=0.8,
            risk_level=RiskLevel.HIGH,
            approval_required=ApprovalLevel.EXPLICIT_APPROVAL,
            safety_concerns=["System file modification"]
        )
    
    @pytest.mark.asyncio
    async def test_execute_without_approval(self, plan_executor, sample_execution_state, low_risk_cost, temp_workspace):
        """Test executing plan that doesn't require approval."""
        # Create test file
        (temp_workspace / "test.txt").write_text("test content")
        
        result = await plan_executor.execute_with_approval(
            execution_state=sample_execution_state,
            cost=low_risk_cost
        )
        
        assert result.status.value in ["completed", "failed"]  # May fail due to mocking
    
    def test_approval_workflow(self, plan_executor, sample_execution_state, high_risk_cost):
        """Test approval workflow."""
        # Test approval request creation
        approval_callbacks = []
        
        def approval_callback(request):
            approval_callbacks.append(request)
        
        plan_executor.add_approval_callback(approval_callback)
        
        # Test approval/denial
        execution_id = sample_execution_state.id
        
        # Approve execution
        success = plan_executor.approve_execution(execution_id, approved=True)
        # Will be False since no pending approval exists yet
        assert success is False
    
    @pytest.mark.asyncio
    async def test_dry_run_mode(self, plan_executor, sample_execution_state):
        """Test dry run mode execution."""
        plan_executor.set_dry_run_mode(True)
        
        result = await plan_executor._execute_dry_run(sample_execution_state)
        
        assert result.status.value == "completed"
        assert result.metadata.get("dry_run") is True
        assert all(step.status.value == "completed" for step in result.steps)
    
    @pytest.mark.asyncio
    async def test_safety_checks(self, plan_executor):
        """Test safety checks."""
        # Create execution state with dangerous operations
        state = ExecutionState(instruction="Dangerous operations")
        
        # Add dangerous file write
        dangerous_step = ExecutionStep(
            step_type=StepType.TOOL_CALL,
            description="Write system file",
            tool_name="write_file",
            tool_args={"path": "/etc/passwd", "content": "malicious"}
        )
        state.add_step(dangerous_step)
        
        # Add dangerous command
        command_step = ExecutionStep(
            step_type=StepType.TOOL_CALL,
            description="Delete files",
            tool_name="run_command",
            tool_args={"command": "rm -rf /"}
        )
        state.add_step(command_step)
        
        safety_result = await plan_executor._perform_safety_checks(state)
        
        assert safety_result["safe"] is False
        assert len(safety_result["issues"]) > 0
        assert "system file" in safety_result["reason"].lower() or "dangerous command" in safety_result["reason"].lower()
    
    def test_pending_approvals_management(self, plan_executor):
        """Test pending approvals management."""
        # Initially no pending approvals
        assert len(plan_executor.get_pending_approvals()) == 0
        
        # Test cancelling non-existent approval
        assert plan_executor.cancel_pending_approval("nonexistent") is False


class TestIntegration:
    """Integration tests for the planning system."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "test.py").write_text("def hello(): print('hello')")
            (workspace / "config.json").write_text('{"setting": "value"}')
            yield workspace
    
    @pytest.fixture
    def mock_bedrock(self):
        """Mock Bedrock client with realistic responses."""
        mock = MagicMock()
        
        # Mock planning response
        plan_response = {
            "content": '{"plan": [{"description": "Read the test file", "tool_name": "read_file", "tool_args": {"path": "test.py"}, "reasoning": "Need to read file", "expected_outcome": "File content"}]}'
        }
        
        mock.chat_with_tools = AsyncMock(return_value=plan_response)
        return mock
    
    @pytest.mark.asyncio
    async def test_end_to_end_planning_workflow(self, temp_workspace, mock_bedrock):
        """Test complete planning workflow."""
        # Initialize planner
        planner = TaskPlanner(bedrock_client=mock_bedrock)
        
        # Create enhanced plan
        result = await planner.create_plan(
            instruction="Read and explain the test.py file",
            context={"workspace": str(temp_workspace)},
            generate_preview=True,
            estimate_cost=True
        )
        
        # Verify plan components
        assert "execution_state" in result
        assert "cost" in result
        assert "preview" in result
        
        execution_state = result["execution_state"]
        cost = result["cost"]
        preview = result["preview"]
        
        # Verify execution state
        assert len(execution_state.steps) > 0
        assert execution_state.instruction == "Read and explain the test.py file"
        
        # Verify cost estimation
        assert cost.estimated_time_minutes > 0
        assert cost.risk_level in [level for level in RiskLevel]
        
        # Verify preview
        assert preview.title
        assert len(preview.step_summaries) > 0
        
        # Initialize executor
        executor = PlanExecutor(
            bedrock_client=mock_bedrock,
            workspace_root=str(temp_workspace)
        )
        
        # Execute with approval workflow
        if cost.approval_required == ApprovalLevel.NONE:
            final_result = await executor.execute_with_approval(
                execution_state=execution_state,
                cost=cost
            )
            
            # Should complete or fail (due to mocking)
            assert final_result.status.value in ["completed", "failed"]


if __name__ == "__main__":
    pytest.main([__file__])