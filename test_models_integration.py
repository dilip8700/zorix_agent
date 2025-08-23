#!/usr/bin/env python3
"""Integration test for data models and schemas."""

import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_models_and_schemas():
    """Test data models and schemas integration."""
    from agent.models.base import (
        Message, MessageRole, ToolCall, ToolResult, CostEstimate,
        SearchResult, PaginatedResponse, ErrorResponse, ErrorType
    )
    from agent.models.plan import (
        PlanStep, StepType, Plan, TaskMode, ExecutionResult, TaskStatus,
        TaskRequest, ChatRequest
    )
    from agent.models.api import (
        SearchRequest, SearchResponse, GitCommitRequest, IndexRebuildResponse
    )
    from agent.llm.schemas import (
        get_all_tool_schemas, get_tool_names, validate_tool_call,
        get_system_prompt_with_tools
    )
    
    print("Testing Data Models and Schemas Integration...")
    
    # Test 1: Basic model creation and validation
    print("✓ Testing basic model creation...")
    
    message = Message(role=MessageRole.USER, content="Hello, Zorix!")
    assert message.role == MessageRole.USER
    assert message.content == "Hello, Zorix!"
    assert isinstance(message.timestamp, datetime)
    
    tool_call = ToolCall(
        id="call_123",
        name="read_file",
        arguments={"path": "test.py"}
    )
    assert tool_call.name == "read_file"
    assert tool_call.arguments["path"] == "test.py"
    
    print("  ✓ Basic models created successfully")
    
    # Test 2: Complex model relationships
    print("✓ Testing complex model relationships...")
    
    # Create a complete plan workflow
    cost_estimate = CostEstimate(
        estimated_tokens=1000,
        estimated_cost_usd=0.05,
        confidence=0.9
    )
    
    steps = [
        PlanStep(
            id="step_1",
            step_type=StepType.TOOL_CALL,
            tool="read_file",
            arguments={"path": "main.py"},
            rationale="Read the main file to understand structure"
        ),
        PlanStep(
            id="step_2",
            step_type=StepType.TOOL_CALL,
            tool="write_file",
            arguments={"path": "new_file.py", "content": "# New file"},
            rationale="Create new file based on analysis"
        )
    ]
    
    from agent.models.plan import PlanPreview
    preview = PlanPreview(
        files_to_create=["new_file.py"],
        files_to_modify=[],
        summary="Create new file based on existing code",
        risk_level="low"
    )
    
    plan = Plan(
        id="plan_123",
        instruction="Create a new Python file",
        mode=TaskMode.CREATE,
        steps=steps,
        cost_estimate=cost_estimate,
        preview=preview,
        requires_approval=False
    )
    
    assert len(plan.steps) == 2
    assert plan.mode == TaskMode.CREATE
    assert plan.requires_approval is False
    
    print("  ✓ Complex plan model created successfully")
    
    # Test 3: API models
    print("✓ Testing API models...")
    
    search_request = SearchRequest(query="def main", top_k=10)
    assert search_request.query == "def main"
    assert search_request.top_k == 10
    
    search_results = [
        SearchResult(
            path="main.py",
            start_line=1,
            end_line=5,
            snippet="def main():\n    print('hello')",
            score=0.95
        )
    ]
    
    search_response = SearchResponse(
        results=search_results,
        total_found=1,
        query="def main",
        duration_ms=150
    )
    
    assert len(search_response.results) == 1
    assert search_response.results[0].score == 0.95
    
    print("  ✓ API models working correctly")
    
    # Test 4: Tool schemas
    print("✓ Testing tool schemas...")
    
    all_schemas = get_all_tool_schemas()
    assert len(all_schemas) > 0
    
    tool_names = get_tool_names()
    expected_tools = ["read_file", "write_file", "run_command", "git_status"]
    for tool in expected_tools:
        assert tool in tool_names
    
    # Test tool validation
    assert validate_tool_call("read_file", {"path": "test.py"}) is True
    assert validate_tool_call("read_file", {}) is False  # Missing required param
    assert validate_tool_call("invalid_tool", {"path": "test.py"}) is False
    
    print("  ✓ Tool schemas validation working")
    
    # Test 5: System prompt generation
    print("✓ Testing system prompt generation...")
    
    prompt = get_system_prompt_with_tools()
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert "Zorix Agent" in prompt
    assert "read_file" in prompt
    assert "security" in prompt.lower()
    assert "workspace" in prompt.lower()
    
    print("  ✓ System prompt generated successfully")
    
    # Test 6: Error handling
    print("✓ Testing error handling...")
    
    error_response = ErrorResponse(
        error_type=ErrorType.VALIDATION_ERROR,
        message="Invalid input provided",
        details={"field": "query", "value": ""},
        suggestion="Provide a non-empty query"
    )
    
    assert error_response.error_type == ErrorType.VALIDATION_ERROR
    assert error_response.suggestion is not None
    
    print("  ✓ Error handling models working")
    
    # Test 7: Pagination
    print("✓ Testing pagination...")
    
    paginated = PaginatedResponse(
        items=["item1", "item2", "item3"],
        total=25,
        page=2,
        page_size=10
    )
    
    assert len(paginated.items) == 3
    assert paginated.total_pages == 3  # ceil(25/10)
    assert paginated.has_next is True  # page 2 < 3
    assert paginated.has_prev is True  # page 2 > 1
    
    print("  ✓ Pagination working correctly")
    
    # Test 8: Validation errors
    print("✓ Testing validation errors...")
    
    try:
        Message(role=MessageRole.USER, content="")  # Should fail
        assert False, "Should have raised validation error"
    except Exception as e:
        assert "cannot be empty" in str(e)
    
    try:
        SearchRequest(query="")  # Should fail
        assert False, "Should have raised validation error"
    except Exception as e:
        assert "cannot be empty" in str(e)
    
    print("  ✓ Validation errors working correctly")
    
    print("🎉 All data models and schemas tests passed!")
    return True


if __name__ == "__main__":
    try:
        if test_models_and_schemas():
            print("\n✅ Data models and schemas integration test - PASSED")
        else:
            print("\n❌ Data models and schemas integration test - FAILED")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)