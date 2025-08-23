"""Tests for tool calling utilities."""

import json
from unittest.mock import patch

import pytest

from agent.llm.tool_calling import (
    ToolCallManager,
    create_tool_error_message,
    create_tool_success_message,
)
from agent.models.base import Message, MessageRole, ToolResult


class TestToolCallManager:
    """Test cases for ToolCallManager."""
    
    @pytest.fixture
    def tool_manager(self):
        """Create ToolCallManager instance."""
        return ToolCallManager(available_tools=["read_file", "write_file", "list_dir"])
    
    @pytest.fixture
    def unrestricted_tool_manager(self):
        """Create ToolCallManager with no tool restrictions."""
        return ToolCallManager(available_tools=None)
    
    def test_validate_tool_calls_valid(self, tool_manager):
        """Test validation of valid tool calls."""
        with patch('agent.llm.tool_calling.validate_tool_call', return_value=True):
            tool_calls = [
                {"name": "read_file", "arguments": {"path": "test.py"}},
                {"name": "write_file", "arguments": {"path": "output.txt", "content": "Hello"}}
            ]
            
            results = tool_manager.validate_tool_calls(tool_calls)
            
            assert len(results) == 2
            assert all(result[0] for result in results)  # All should be valid
            assert all(result[1] == "" for result in results)  # No error messages
    
    def test_validate_tool_calls_invalid_tool(self, tool_manager):
        """Test validation with unavailable tool."""
        tool_calls = [
            {"name": "invalid_tool", "arguments": {}}
        ]
        
        results = tool_manager.validate_tool_calls(tool_calls)
        
        assert len(results) == 1
        assert not results[0][0]  # Should be invalid
        assert "not available" in results[0][1]
    
    def test_validate_tool_calls_missing_name(self, tool_manager):
        """Test validation with missing tool name."""
        tool_calls = [
            {"arguments": {"path": "test.py"}}  # Missing name
        ]
        
        results = tool_manager.validate_tool_calls(tool_calls)
        
        assert len(results) == 1
        assert not results[0][0]  # Should be invalid
        assert "Tool name is required" in results[0][1]
    
    def test_validate_tool_calls_schema_validation_failure(self, tool_manager):
        """Test validation with schema validation failure."""
        with patch('agent.llm.tool_calling.validate_tool_call', return_value=False):
            tool_calls = [
                {"name": "read_file", "arguments": {"invalid": "args"}}
            ]
            
            results = tool_manager.validate_tool_calls(tool_calls)
            
            assert len(results) == 1
            assert not results[0][0]  # Should be invalid
            assert "Invalid arguments" in results[0][1]
    
    def test_validate_tool_calls_unrestricted(self, unrestricted_tool_manager):
        """Test validation with unrestricted tool manager."""
        with patch('agent.llm.tool_calling.validate_tool_call', return_value=True):
            tool_calls = [
                {"name": "any_tool", "arguments": {}}
            ]
            
            results = unrestricted_tool_manager.validate_tool_calls(tool_calls)
            
            assert len(results) == 1
            assert results[0][0]  # Should be valid
    
    def test_create_tool_call_messages(self, tool_manager):
        """Test creating messages for tool calls and results."""
        tool_calls = [
            {"name": "read_file", "arguments": {"path": "test.py"}}
        ]
        
        tool_results = [
            ToolResult(
                tool_call_id="call_123",
                success=True,
                result="File content here",
                duration_ms=150
            )
        ]
        
        messages = tool_manager.create_tool_call_messages(tool_calls, tool_results)
        
        assert len(messages) == 2
        
        # Check assistant message with tool calls
        assistant_msg = messages[0]
        assert assistant_msg.role == MessageRole.ASSISTANT
        assert "read_file" in assistant_msg.content
        assert "tool_calls" in assistant_msg.metadata
        
        # Check tool result message
        tool_msg = messages[1]
        assert tool_msg.role == MessageRole.TOOL
        assert "successful" in tool_msg.content
        assert "150ms" in tool_msg.content
        assert tool_msg.metadata["tool_call_id"] == "call_123"
        assert tool_msg.metadata["success"] is True
    
    def test_format_tool_calls_for_message(self, tool_manager):
        """Test formatting tool calls for message content."""
        tool_calls = [
            {"name": "read_file", "arguments": {"path": "test.py"}},
            {"name": "write_file", "arguments": {}}
        ]
        
        content = tool_manager._format_tool_calls_for_message(tool_calls)
        
        assert "Calling read_file with arguments:" in content
        assert "Calling write_file with no arguments" in content
        assert '"path": "test.py"' in content
    
    def test_format_tool_result_for_message_success(self, tool_manager):
        """Test formatting successful tool result."""
        result = ToolResult(
            tool_call_id="call_123",
            success=True,
            result={"status": "ok", "data": "test"},
            duration_ms=100
        )
        
        content = tool_manager._format_tool_result_for_message(result)
        
        assert "Tool execution successful" in content
        assert "took 100ms" in content
        assert '"status": "ok"' in content
    
    def test_format_tool_result_for_message_failure(self, tool_manager):
        """Test formatting failed tool result."""
        result = ToolResult(
            tool_call_id="call_123",
            success=False,
            error="File not found"
        )
        
        content = tool_manager._format_tool_result_for_message(result)
        
        assert "Tool execution failed" in content
        assert "File not found" in content
    
    def test_extract_tool_calls_from_response(self, tool_manager):
        """Test extracting tool calls from LLM response."""
        # Response with tool calls
        response_with_tools = {
            "type": "tool_calls",
            "tool_calls": [
                {"name": "read_file", "arguments": {"path": "test.py"}}
            ]
        }
        
        tool_calls = tool_manager.extract_tool_calls_from_response(response_with_tools)
        assert len(tool_calls) == 1
        assert tool_calls[0]["name"] == "read_file"
        
        # Response without tool calls
        response_without_tools = {
            "type": "text",
            "content": "Hello world"
        }
        
        tool_calls = tool_manager.extract_tool_calls_from_response(response_without_tools)
        assert len(tool_calls) == 0
    
    def test_should_continue_conversation(self, tool_manager):
        """Test conversation continuation logic."""
        # Response with tool calls - should continue
        response_with_tools = {
            "type": "tool_calls",
            "tool_calls": [{"name": "read_file"}]
        }
        
        assert tool_manager.should_continue_conversation(response_with_tools, max_iterations=5, current_iteration=1)
        
        # Response without tool calls - should not continue
        response_without_tools = {
            "type": "text",
            "content": "Done"
        }
        
        assert not tool_manager.should_continue_conversation(response_without_tools, max_iterations=5, current_iteration=1)
        
        # Max iterations reached - should not continue
        assert not tool_manager.should_continue_conversation(response_with_tools, max_iterations=5, current_iteration=5)
    
    def test_create_system_message_with_tools(self, tool_manager):
        """Test creating system message with tool information."""
        with patch('agent.llm.tool_calling.get_system_prompt_with_tools', return_value="Tool instructions here"):
            base_prompt = "You are a helpful assistant."
            
            message = tool_manager.create_system_message_with_tools(base_prompt)
            
            assert message.role == MessageRole.SYSTEM
            assert "helpful assistant" in message.content
            assert "Tool instructions here" in message.content
            assert "available_tools" in message.metadata
    
    def test_estimate_tokens_for_tools(self, tool_manager):
        """Test token estimation for tool schemas."""
        tool_schemas = [
            {
                "name": "read_file",
                "description": "Read a file",
                "input_schema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}}
                }
            }
        ]
        
        token_count = tool_manager.estimate_tokens_for_tools(tool_schemas)
        
        assert isinstance(token_count, int)
        assert token_count > 0
    
    def test_get_tool_usage_stats(self, tool_manager):
        """Test getting tool usage statistics."""
        messages = [
            Message(
                role=MessageRole.ASSISTANT,
                content="I'll read the file",
                metadata={"tool_calls": [{"name": "read_file"}]}
            ),
            Message(
                role=MessageRole.TOOL,
                content="File content",
                metadata={"tool_call_id": "call_123", "success": True, "duration_ms": 100}
            ),
            Message(
                role=MessageRole.ASSISTANT,
                content="I'll write a file",
                metadata={"tool_calls": [{"name": "write_file"}]}
            ),
            Message(
                role=MessageRole.TOOL,
                content="Write failed",
                metadata={"tool_call_id": "call_456", "success": False}
            )
        ]
        
        stats = tool_manager.get_tool_usage_stats(messages)
        
        assert stats["total_tool_calls"] == 2
        assert stats["successful_calls"] == 1
        assert stats["failed_calls"] == 1
        assert stats["tools_used"]["read_file"] == 1
        assert stats["tools_used"]["write_file"] == 1
        assert stats["average_duration_ms"] == 100


class TestToolMessageCreation:
    """Test cases for tool message creation functions."""
    
    def test_create_tool_error_message(self):
        """Test creating tool error message."""
        message = create_tool_error_message("call_123", "File not found")
        
        assert message.role == MessageRole.TOOL
        assert "Tool execution failed" in message.content
        assert "File not found" in message.content
        assert message.metadata["tool_call_id"] == "call_123"
        assert message.metadata["success"] is False
        assert message.metadata["error"] == "File not found"
    
    def test_create_tool_success_message_with_duration(self):
        """Test creating tool success message with duration."""
        result = {"status": "ok", "data": "test"}
        message = create_tool_success_message("call_123", result, duration_ms=150)
        
        assert message.role == MessageRole.TOOL
        assert "Tool execution successful" in message.content
        assert "took 150ms" in message.content
        assert '"status": "ok"' in message.content
        assert message.metadata["tool_call_id"] == "call_123"
        assert message.metadata["success"] is True
        assert message.metadata["result"] == result
        assert message.metadata["duration_ms"] == 150
    
    def test_create_tool_success_message_without_duration(self):
        """Test creating tool success message without duration."""
        result = "Simple string result"
        message = create_tool_success_message("call_123", result)
        
        assert message.role == MessageRole.TOOL
        assert "Tool execution successful" in message.content
        assert "took" not in message.content  # No duration info
        assert "Simple string result" in message.content
        assert message.metadata["tool_call_id"] == "call_123"
        assert message.metadata["success"] is True
        assert message.metadata["result"] == result
        assert "duration_ms" not in message.metadata