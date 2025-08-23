#!/usr/bin/env python3
"""Simple orchestrator test without Bedrock dependency."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from agent.orchestrator.core import AgentOrchestrator
from agent.orchestrator.state import ExecutionStatus


async def test_orchestrator_simple():
    """Test orchestrator with mocked Bedrock client."""
    print("🤖 Testing Agent Orchestrator (Simple)...")
    
    # Create temporary workspace
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace_path = Path(temp_dir)
        
        # Create test files
        (workspace_path / "test.txt").write_text("Hello, World!")
        (workspace_path / "data.json").write_text('{"name": "test", "version": "1.0"}')
        
        print(f"✅ Created test workspace at {workspace_path}")
        
        # Create mock Bedrock client
        mock_bedrock = MagicMock()
        
        # Mock planning response
        plan_response = {
            "content": '{"plan": [{"description": "Read the test.txt file", "tool_name": "read_file", "tool_args": {"path": "test.txt"}, "reasoning": "Need to read the file", "expected_outcome": "File content"}]}'
        }
        mock_bedrock.chat_with_tools = AsyncMock(return_value=plan_response)
        
        # Initialize orchestrator with mock
        orchestrator = AgentOrchestrator(
            bedrock_client=mock_bedrock,
            workspace_root=str(workspace_path)
        )
        
        print("✅ Orchestrator initialized with mock Bedrock")
        
        # Test 1: Simple file reading task
        print("\n📖 Testing simple file reading task...")
        
        result = await orchestrator.execute_instruction(
            instruction="Read the test.txt file",
            context={"task_type": "file_reading"}
        )
        
        print(f"✅ Task completed with status: {result.status.value}")
        print(f"   - Total steps: {len(result.steps)}")
        print(f"   - Completed steps: {len([s for s in result.steps if s.status == ExecutionStatus.COMPLETED])}")
        
        if result.steps:
            print(f"   - First step: {result.steps[0].description}")
            if result.steps[0].result:
                result_str = str(result.steps[0].result)
                if len(result_str) > 100:
                    result_str = result_str[:100] + "..."
                print(f"   - Result: {result_str}")
        
        # Test 2: Directory listing task
        print("\n📁 Testing directory listing task...")
        
        # Update mock for directory listing
        list_response = {
            "content": '{"plan": [{"description": "List directory contents", "tool_name": "list_directory", "tool_args": {"path": "."}, "reasoning": "Need to see files", "expected_outcome": "Directory listing"}]}'
        }
        mock_bedrock.chat_with_tools = AsyncMock(return_value=list_response)
        
        result = await orchestrator.execute_instruction(
            instruction="List all files in the current directory",
            context={"task_type": "directory_listing"}
        )
        
        print(f"✅ Directory listing completed with status: {result.status.value}")
        print(f"   - Total steps: {len(result.steps)}")
        
        # Test 3: Multi-step task
        print("\n🔄 Testing multi-step task...")
        
        multi_step_response = {
            "content": '{"plan": [{"description": "Read test.txt", "tool_name": "read_file", "tool_args": {"path": "test.txt"}, "reasoning": "Read first file", "expected_outcome": "File content"}, {"description": "Read data.json", "tool_name": "read_file", "tool_args": {"path": "data.json"}, "reasoning": "Read second file", "expected_outcome": "JSON data"}]}'
        }
        mock_bedrock.chat_with_tools = AsyncMock(return_value=multi_step_response)
        
        result = await orchestrator.execute_instruction(
            instruction="Read both test.txt and data.json files",
            context={"task_type": "multi_file"}
        )
        
        print(f"✅ Multi-step task completed with status: {result.status.value}")
        print(f"   - Total steps: {len(result.steps)}")
        
        for i, step in enumerate(result.steps, 1):
            print(f"   - Step {i}: {step.description} ({step.status.value})")
        
        # Test 4: Test execution state management
        print("\n⚙️ Testing execution state management...")
        
        # Check progress tracking
        progress = result.get_progress()
        print(f"   - Progress: {progress['progress_percentage']:.1f}%")
        print(f"   - Completed: {progress['completed_steps']}/{progress['total_steps']}")
        
        # Test rollback points
        if result.rollback_points:
            print(f"   - Rollback points: {len(result.rollback_points)}")
        
        # Test 5: Tool availability
        print("\n🔧 Testing tool availability...")
        
        available_tools = orchestrator.executor.get_available_tools()
        print(f"   - Available tools: {len(available_tools)}")
        print(f"   - Tools: {', '.join(available_tools[:5])}{'...' if len(available_tools) > 5 else ''}")
        
        # Test 6: Context preservation
        print("\n🔗 Testing context preservation...")
        
        # Check if context is preserved between steps
        if result.context:
            print(f"   - Context keys: {list(result.context.keys())}")
            print(f"   - Context entries: {len(result.context)}")
        
        print("\n🎉 Simple orchestrator test completed successfully!")
        
        return True


async def test_orchestrator_error_handling():
    """Test error handling in orchestrator."""
    print("\n🔧 Testing Error Handling...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace_path = Path(temp_dir)
        
        # Create mock that simulates errors
        mock_bedrock = MagicMock()
        
        # Mock response for non-existent file
        error_response = {
            "content": '{"plan": [{"description": "Read non-existent file", "tool_name": "read_file", "tool_args": {"path": "nonexistent.txt"}, "reasoning": "Try to read file", "expected_outcome": "File content"}]}'
        }
        mock_bedrock.chat_with_tools = AsyncMock(return_value=error_response)
        
        orchestrator = AgentOrchestrator(
            bedrock_client=mock_bedrock,
            workspace_root=str(workspace_path)
        )
        
        # Test error handling
        result = await orchestrator.execute_instruction(
            "Read a file that doesn't exist: nonexistent.txt"
        )
        
        print(f"✅ Error handling test completed")
        print(f"   - Status: {result.status.value}")
        
        if result.status == ExecutionStatus.FAILED:
            print("   - Expected failure for nonexistent file ✓")
            failed_steps = [s for s in result.steps if s.status == ExecutionStatus.FAILED]
            if failed_steps:
                print(f"   - Failed step: {failed_steps[0].description}")
                print(f"   - Error: {failed_steps[0].error}")
        
        print("🔧 Error handling test completed!")


if __name__ == "__main__":
    async def main():
        try:
            await test_orchestrator_simple()
            await test_orchestrator_error_handling()
            print("\n🎉 All simple orchestrator tests passed!")
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        return True
    
    # Run the test
    success = asyncio.run(main())
    exit(0 if success else 1)