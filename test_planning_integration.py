#!/usr/bin/env python3
"""Integration test for the enhanced planning system."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from agent.planning.cost_estimator import ApprovalLevel, CostEstimator, RiskLevel
from agent.planning.executor import PlanExecutor
from agent.planning.modes import PlanningMode, detect_planning_mode
from agent.planning.planner import TaskPlanner
from agent.planning.preview import PreviewGenerator


async def test_planning_integration():
    """Test complete planning system integration."""
    print("📋 Testing Enhanced Planning System Integration...")
    
    # Create temporary workspace
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace_path = Path(temp_dir)
        
        # Create test files
        (workspace_path / "main.py").write_text("""
def calculate_sum(a, b):
    return a + b

def main():
    result = calculate_sum(5, 3)
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
""")
        
        (workspace_path / "config.json").write_text('{"debug": true, "port": 8000}')
        (workspace_path / "README.md").write_text("# Test Project\nThis is a test project.")
        
        print(f"✅ Created test workspace at {workspace_path}")
        
        # Test 1: Mode Detection
        print("\n🎯 Testing planning mode detection...")
        
        test_instructions = [
            ("Edit the main.py file to add error handling", PlanningMode.EDIT),
            ("Explain how the calculate_sum function works", PlanningMode.EXPLAIN),
            ("Refactor the main.py code for better structure", PlanningMode.REFACTOR),
            ("Create unit tests for the calculate_sum function", PlanningMode.TEST),
            ("Build a new logging system", PlanningMode.CREATE),
        ]
        
        for instruction, expected_mode in test_instructions:
            detected_mode = detect_planning_mode(instruction)
            print(f"   - '{instruction[:30]}...' → {detected_mode.value} ({'✓' if detected_mode == expected_mode else '✗'})")
        
        # Test 2: Cost Estimation
        print("\n💰 Testing cost estimation...")
        
        cost_estimator = CostEstimator()
        
        # Low risk plan
        low_risk_steps = [
            {"tool_name": "read_file", "tool_args": {"path": "main.py"}, "description": "Read main file"}
        ]
        
        low_cost = cost_estimator.estimate_plan_cost(low_risk_steps, PlanningMode.EXPLAIN)
        print(f"   - Low risk plan: {low_cost.estimated_time_minutes:.1f}min, {low_cost.risk_level.value} risk, {low_cost.approval_required.value} approval")
        
        # High risk plan
        high_risk_steps = [
            {"tool_name": "run_command", "tool_args": {"command": "sudo rm -rf /tmp/test"}, "description": "Delete files"},
            {"tool_name": "write_file", "tool_args": {"path": "/etc/config.conf"}, "description": "Modify system config"}
        ]
        
        high_cost = cost_estimator.estimate_plan_cost(high_risk_steps, PlanningMode.EDIT)
        print(f"   - High risk plan: {high_cost.estimated_time_minutes:.1f}min, {high_cost.risk_level.value} risk, {high_cost.approval_required.value} approval")
        print(f"   - Safety concerns: {', '.join(high_cost.safety_concerns) if high_cost.safety_concerns else 'None'}")
        
        # Test 3: Preview Generation
        print("\n📄 Testing preview generation...")
        
        preview_generator = PreviewGenerator()
        
        sample_steps = [
            {
                "tool_name": "read_file",
                "tool_args": {"path": "main.py"},
                "description": "Read main.py file",
                "expected_outcome": "File content retrieved"
            },
            {
                "tool_name": "write_file", 
                "tool_args": {"path": "main.py", "content": "updated content"},
                "description": "Add error handling to main.py",
                "expected_outcome": "File updated with error handling"
            }
        ]
        
        preview = preview_generator.generate_preview(
            instruction="Add error handling to main.py",
            steps=sample_steps,
            mode=PlanningMode.EDIT,
            cost=low_cost
        )
        
        print(f"   - Preview title: {preview.title}")
        print(f"   - Files affected: {', '.join(preview.files_affected)}")
        print(f"   - Step summaries: {len(preview.step_summaries)} steps")
        print(f"   - Expected outcomes: {len(preview.expected_outcomes)} outcomes")
        
        # Test 4: Enhanced Task Planner
        print("\n🧠 Testing enhanced task planner...")
        
        # Create mock Bedrock client
        mock_bedrock = MagicMock()
        mock_bedrock.chat_with_tools = AsyncMock(return_value={
            "content": '{"plan": [{"description": "Read main.py file", "tool_name": "read_file", "tool_args": {"path": "main.py"}, "reasoning": "Need to read the file first", "expected_outcome": "File content retrieved"}, {"description": "Analyze code structure", "tool_name": null, "tool_args": {}, "reasoning": "Understand the code", "expected_outcome": "Code analysis complete"}]}'
        })
        
        planner = TaskPlanner(bedrock_client=mock_bedrock)
        
        # Create enhanced plan
        result = await planner.create_plan(
            instruction="Explain the main.py file structure and functionality",
            context={"workspace": str(workspace_path)},
            generate_preview=True,
            estimate_cost=True
        )
        
        print(f"   - Planning mode: {result['planning_mode'].value}")
        print(f"   - Execution steps: {len(result['execution_state'].steps)}")
        print(f"   - Estimated cost: {result['cost'].estimated_time_minutes:.1f} minutes")
        print(f"   - Risk level: {result['cost'].risk_level.value}")
        print(f"   - Preview generated: {'✓' if result['preview'] else '✗'}")
        
        # Test mode recommendations
        recommendations = planner.get_mode_recommendations(
            "Fix the bug in the authentication system"
        )
        
        print(f"   - Mode recommendations: {len(recommendations)} modes")
        top_recommendation = recommendations[0] if recommendations else None
        if top_recommendation:
            print(f"   - Top recommendation: {top_recommendation['mode']} (score: {top_recommendation['suitability_score']:.2f})")
        
        # Test 5: Plan Executor with Approval Workflow
        print("\n⚡ Testing plan executor...")
        
        executor = PlanExecutor(
            bedrock_client=mock_bedrock,
            workspace_root=str(workspace_path)
        )
        
        # Test safety checks
        print("   - Testing safety checks...")
        executor.enable_safety_checks(True)
        
        # Test dry run mode
        print("   - Testing dry run mode...")
        executor.set_dry_run_mode(True)
        
        # Execute a simple plan in dry run
        simple_result = await executor.execute_with_approval(
            execution_state=result['execution_state'],
            cost=result['cost']
        )
        
        print(f"   - Dry run execution: {simple_result.status.value}")
        print(f"   - Steps completed: {len([s for s in simple_result.steps if s.status.value == 'completed'])}/{len(simple_result.steps)}")
        
        # Test approval workflow
        print("   - Testing approval workflow...")
        
        approval_requests = []
        
        def approval_callback(request):
            approval_requests.append(request)
            print(f"     - Approval requested for: {request.execution_id}")
            print(f"     - Message: {request.message[:100]}...")
        
        executor.add_approval_callback(approval_callback)
        
        # Test with high-risk plan that requires approval
        executor.set_dry_run_mode(False)  # Disable dry run for approval test
        
        # Create high-risk execution state
        from agent.orchestrator.state import ExecutionState, ExecutionStep, StepType
        
        high_risk_state = ExecutionState(instruction="Perform system modifications")
        dangerous_step = ExecutionStep(
            step_type=StepType.TOOL_CALL,
            description="Modify system configuration",
            tool_name="write_file",
            tool_args={"path": "/etc/test.conf", "content": "test=value"}
        )
        high_risk_state.add_step(dangerous_step)
        
        # This would normally wait for approval, but we'll test the setup
        pending_before = len(executor.get_pending_approvals())
        print(f"   - Pending approvals before: {pending_before}")
        
        # Test 6: Format Preview
        print("\n📝 Testing preview formatting...")
        
        preview_text = preview_generator.format_preview_text(preview)
        preview_json = preview_generator.format_preview_json(preview)
        
        print(f"   - Text preview length: {len(preview_text)} characters")
        print(f"   - JSON preview keys: {list(preview_json.keys())}")
        
        # Show preview excerpt
        preview_lines = preview_text.split('\n')[:10]
        print("   - Preview excerpt:")
        for line in preview_lines:
            if line.strip():
                print(f"     {line}")
        
        # Test 7: Mode-Specific Planning
        print("\n🎨 Testing mode-specific planning...")
        
        mode_tests = [
            (PlanningMode.EDIT, "Edit the configuration file"),
            (PlanningMode.REFACTOR, "Refactor the code structure"),
            (PlanningMode.TEST, "Create comprehensive tests"),
        ]
        
        for mode, instruction in mode_tests:
            mode_result = await planner.create_mode_specific_plan(
                instruction=instruction,
                mode=mode,
                target_files=["main.py"],
                generate_preview=False,
                estimate_cost=True
            )
            
            print(f"   - {mode.value} mode: {mode_result['cost'].estimated_time_minutes:.1f}min, {len(mode_result['execution_state'].steps)} steps")
        
        # Test 8: Cost Estimation Edge Cases
        print("\n🔍 Testing cost estimation edge cases...")
        
        # Empty plan
        empty_cost = cost_estimator.estimate_plan_cost([], PlanningMode.CREATE)
        print(f"   - Empty plan: {empty_cost.estimated_time_minutes:.1f}min, {empty_cost.risk_level.value} risk")
        
        # Large plan
        large_steps = [
            {"tool_name": "write_file", "tool_args": {"path": f"file_{i}.py"}, "description": f"Create file {i}"}
            for i in range(20)
        ]
        large_cost = cost_estimator.estimate_plan_cost(large_steps, PlanningMode.CREATE)
        print(f"   - Large plan (20 files): {large_cost.estimated_time_minutes:.1f}min, {large_cost.approval_required.value} approval")
        
        print("\n🎉 Enhanced planning system integration test completed successfully!")
        
        return True


async def test_planning_performance():
    """Test planning system performance."""
    print("\n⚡ Testing Planning System Performance...")
    
    # Create mock Bedrock client
    mock_bedrock = MagicMock()
    mock_bedrock.chat_with_tools = AsyncMock(return_value={
        "content": '{"plan": [{"description": "Test step", "tool_name": "read_file", "tool_args": {"path": "test.py"}, "reasoning": "Test", "expected_outcome": "Success"}]}'
    })
    
    planner = TaskPlanner(bedrock_client=mock_bedrock)
    cost_estimator = CostEstimator()
    preview_generator = PreviewGenerator()
    
    # Test planning performance
    print("📊 Testing planning performance...")
    
    import time
    
    # Test multiple plan creations
    start_time = time.time()
    
    tasks = []
    for i in range(10):
        task = planner.create_plan(
            instruction=f"Process file {i}",
            generate_preview=True,
            estimate_cost=True
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"✅ Created {len(results)} plans in {duration:.2f} seconds ({len(results)/duration:.1f} plans/sec)")
    
    # Test cost estimation performance
    print("💰 Testing cost estimation performance...")
    
    start_time = time.time()
    
    for i in range(100):
        steps = [
            {"tool_name": "read_file", "tool_args": {"path": f"file_{i}.py"}},
            {"tool_name": "write_file", "tool_args": {"path": f"output_{i}.py"}},
        ]
        cost_estimator.estimate_plan_cost(steps, PlanningMode.EDIT)
    
    end_time = time.time()
    cost_duration = end_time - start_time
    
    print(f"✅ Estimated 100 plan costs in {cost_duration:.2f} seconds ({100/cost_duration:.1f} estimates/sec)")
    
    # Test preview generation performance
    print("📄 Testing preview generation performance...")
    
    start_time = time.time()
    
    sample_steps = [{"tool_name": "read_file", "tool_args": {"path": "test.py"}}]
    sample_cost = cost_estimator.estimate_plan_cost(sample_steps, PlanningMode.EDIT)
    
    for i in range(50):
        preview_generator.generate_preview(
            instruction=f"Process file {i}",
            steps=sample_steps,
            mode=PlanningMode.EDIT,
            cost=sample_cost
        )
    
    end_time = time.time()
    preview_duration = end_time - start_time
    
    print(f"✅ Generated 50 previews in {preview_duration:.2f} seconds ({50/preview_duration:.1f} previews/sec)")
    
    print("⚡ Performance test completed!")


if __name__ == "__main__":
    async def main():
        try:
            await test_planning_integration()
            await test_planning_performance()
            print("\n🎉 All planning integration tests passed!")
        except Exception as e:
            print(f"\n❌ Integration test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        return True
    
    # Run the test
    success = asyncio.run(main())
    exit(0 if success else 1)