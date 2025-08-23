#!/usr/bin/env python3
"""Integration test for the agent orchestrator system."""

import asyncio
import json
import tempfile
from pathlib import Path

from agent.orchestrator.core import AgentOrchestrator
from agent.orchestrator.state import ExecutionStatus


async def test_orchestrator_integration():
    """Test complete orchestrator system integration."""
    print("🤖 Testing Agent Orchestrator Integration...")
    
    # Create temporary workspace
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace_path = Path(temp_dir)
        
        # Create test files
        (workspace_path / "README.md").write_text("# Test Project\nThis is a test project for the orchestrator.")
        (workspace_path / "src").mkdir()
        (workspace_path / "src" / "main.py").write_text("""
def hello_world():
    print("Hello from the orchestrator test!")

if __name__ == "__main__":
    hello_world()
""")
        (workspace_path / "data.json").write_text('{"name": "test", "version": "1.0.0"}')
        
        print(f"✅ Created test workspace at {workspace_path}")
        
        # Initialize orchestrator
        orchestrator = AgentOrchestrator(workspace_root=str(workspace_path))
        
        print("✅ Orchestrator initialized")
        
        # Test 1: Simple file reading task
        print("\n📖 Testing simple file reading task...")
        
        result = await orchestrator.execute_instruction(
            instruction="Read the README.md file and tell me what it contains",
            context={"task_type": "file_reading"}
        )
        
        print(f"✅ File reading task completed with status: {result.status.value}")
        print(f"   - Total steps: {len(result.steps)}")
        print(f"   - Completed steps: {len([s for s in result.steps if s.status == ExecutionStatus.COMPLETED])}")
        
        if result.steps:
            print(f"   - First step: {result.steps[0].description}")
            if result.steps[0].result:
                print(f"   - Result preview: {str(result.steps[0].result)[:100]}...")
        
        # Test 2: Multi-step task with directory listing
        print("\n📁 Testing multi-step directory analysis task...")
        
        result = await orchestrator.execute_instruction(
            instruction="List all files in the workspace and analyze the project structure",
            context={"task_type": "analysis"}
        )
        
        print(f"✅ Directory analysis completed with status: {result.status.value}")
        print(f"   - Total steps: {len(result.steps)}")
        
        for i, step in enumerate(result.steps, 1):
            print(f"   - Step {i}: {step.description} ({step.status.value})")
        
        # Test 3: Streaming execution
        print("\n🌊 Testing streaming execution...")
        
        events = []
        event_types = set()
        
        async for event in orchestrator.execute_instruction(
            instruction="Read the data.json file and list the src directory",
            streaming=True
        ):
            events.append(event)
            event_types.add(event.event_type)
            
            print(f"   📡 Event: {event.event_type}")
            
            if event.event_type == "execution_completed":
                break
        
        print(f"✅ Streaming execution completed")
        print(f"   - Total events: {len(events)}")
        print(f"   - Event types: {sorted(event_types)}")
        
        # Test 4: Error handling and recovery
        print("\n🔧 Testing error handling...")
        
        result = await orchestrator.execute_instruction(
            instruction="Read a file that doesn't exist: nonexistent.txt",
            context={"task_type": "error_test"}
        )
        
        print(f"✅ Error handling test completed with status: {result.status.value}")
        
        if result.status == ExecutionStatus.FAILED:
            print("   - Expected failure for nonexistent file")
            failed_steps = [s for s in result.steps if s.status == ExecutionStatus.FAILED]
            if failed_steps:
                print(f"   - Failed step: {failed_steps[0].description}")
                print(f"   - Error: {failed_steps[0].error}")
        
        # Test 5: Complex reasoning task
        print("\n🧠 Testing reasoning capabilities...")
        
        result = await orchestrator.execute_instruction(
            instruction="Analyze the Python code in src/main.py and explain what it does",
            context={"task_type": "code_analysis"}
        )
        
        print(f"✅ Code analysis completed with status: {result.status.value}")
        
        reasoning_steps = [s for s in result.steps if s.step_type.value == "reasoning"]
        if reasoning_steps:
            print(f"   - Found {len(reasoning_steps)} reasoning steps")
            print(f"   - Reasoning result preview: {str(reasoning_steps[0].result)[:150]}...")
        
        # Test 6: Execution management
        print("\n⚙️ Testing execution management...")
        
        # Start a long-running task
        execution_task = asyncio.create_task(
            orchestrator.execute_instruction(
                "Read all files in the workspace and create a detailed report"
            )
        )
        
        # Give it a moment to start
        await asyncio.sleep(0.1)
        
        # Check active executions
        active_executions = orchestrator.get_active_executions()
        print(f"   - Active executions: {len(active_executions)}")
        
        # Wait for completion
        result = await execution_task
        print(f"✅ Long-running task completed: {result.status.value}")
        
        # Test 7: Plan quality assessment
        print("\n📋 Testing plan quality...")
        
        # Test with a complex instruction
        result = await orchestrator.execute_instruction(
            instruction="Create a backup of all Python files by copying them to a backup directory",
            context={"task_type": "file_operations"}
        )
        
        print(f"✅ Complex task completed with status: {result.status.value}")
        print(f"   - Plan had {len(result.plan)} high-level steps:")
        for i, step_desc in enumerate(result.plan, 1):
            print(f"     {i}. {step_desc}")
        
        # Test 8: Context preservation
        print("\n🔗 Testing context preservation...")
        
        # Execute task that should build context
        result1 = await orchestrator.execute_instruction(
            "Read the data.json file and remember its contents"
        )
        
        # Execute follow-up task that should use the context
        result2 = await orchestrator.execute_instruction(
            "Based on what you read from data.json, what is the project name?"
        )
        
        print(f"✅ Context preservation test completed")
        print(f"   - First task: {result1.status.value}")
        print(f"   - Second task: {result2.status.value}")
        
        # Check if context was preserved
        if result2.context:
            print(f"   - Context keys: {list(result2.context.keys())}")
        
        print("\n🎉 Agent Orchestrator integration test completed successfully!")
        
        return True


async def test_orchestrator_performance():
    """Test orchestrator performance with multiple concurrent tasks."""
    print("\n⚡ Testing Orchestrator Performance...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace_path = Path(temp_dir)
        
        # Create multiple test files
        for i in range(10):
            (workspace_path / f"file_{i}.txt").write_text(f"Content of file {i}")
        
        orchestrator = AgentOrchestrator(workspace_root=str(workspace_path))
        
        # Test concurrent executions
        print("🔄 Testing concurrent executions...")
        
        import time
        start_time = time.time()
        
        tasks = []
        for i in range(5):
            task = orchestrator.execute_instruction(
                f"Read file_{i}.txt and count the words in it"
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"✅ Completed {len(tasks)} concurrent tasks in {duration:.2f} seconds")
        
        successful_tasks = sum(1 for result in results if result.status == ExecutionStatus.COMPLETED)
        print(f"   - Successful tasks: {successful_tasks}/{len(tasks)}")
        print(f"   - Average time per task: {duration/len(tasks):.2f} seconds")
        
        # Test streaming performance
        print("🌊 Testing streaming performance...")
        
        start_time = time.time()
        event_count = 0
        
        async for event in orchestrator.execute_instruction(
            "Read all files and create a summary report",
            streaming=True
        ):
            event_count += 1
            if event.event_type == "execution_completed":
                break
        
        end_time = time.time()
        streaming_duration = end_time - start_time
        
        print(f"✅ Streaming execution completed in {streaming_duration:.2f} seconds")
        print(f"   - Total events: {event_count}")
        print(f"   - Events per second: {event_count/streaming_duration:.1f}")
        
        print("⚡ Performance test completed!")


if __name__ == "__main__":
    async def main():
        try:
            await test_orchestrator_integration()
            await test_orchestrator_performance()
            print("\n🎉 All orchestrator integration tests passed!")
        except Exception as e:
            print(f"\n❌ Integration test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        return True
    
    # Run the test
    success = asyncio.run(main())
    exit(0 if success else 1)