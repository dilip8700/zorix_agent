"""Utilities for LLM tool calling."""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from agent.llm.schemas import get_tool_schema_by_name, validate_tool_call
from agent.models.base import Message, MessageRole, ToolCall, ToolResult

logger = logging.getLogger(__name__)


class ToolCallManager:
    """Manages tool calling workflow and validation."""
    
    def __init__(self, available_tools: Optional[List[str]] = None):
        """Initialize tool call manager.
        
        Args:
            available_tools: List of available tool names. If None, all tools are available.
        """
        self.available_tools = available_tools
    
    def validate_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Tuple[bool, str]]:
        """Validate a list of tool calls.
        
        Args:
            tool_calls: List of tool call dictionaries
            
        Returns:
            List of (is_valid, error_message) tuples
        """
        results = []
        
        for tool_call in tool_calls:
            try:
                tool_name = tool_call.get('name')
                arguments = tool_call.get('arguments', {})
                
                if not tool_name:
                    results.append((False, "Tool name is required"))
                    continue
                
                # Check if tool is available
                if self.available_tools and tool_name not in self.available_tools:
                    results.append((False, f"Tool '{tool_name}' is not available"))
                    continue
                
                # Validate against schema
                if validate_tool_call(tool_name, arguments):
                    results.append((True, ""))
                else:
                    results.append((False, f"Invalid arguments for tool '{tool_name}'"))
                    
            except Exception as e:
                results.append((False, f"Validation error: {e}"))
        
        return results
    
    def create_tool_call_messages(
        self,
        tool_calls: List[Dict[str, Any]],
        tool_results: List[ToolResult]
    ) -> List[Message]:
        """Create messages for tool calls and results.
        
        Args:
            tool_calls: List of tool call dictionaries
            tool_results: List of tool execution results
            
        Returns:
            List of messages representing the tool calling conversation
        """
        messages = []
        
        # Create assistant message with tool calls
        if tool_calls:
            tool_call_content = self._format_tool_calls_for_message(tool_calls)
            messages.append(Message(
                role=MessageRole.ASSISTANT,
                content=tool_call_content,
                metadata={"tool_calls": tool_calls}
            ))
        
        # Create tool result messages
        for result in tool_results:
            tool_content = self._format_tool_result_for_message(result)
            messages.append(Message(
                role=MessageRole.TOOL,
                content=tool_content,
                metadata={
                    "tool_call_id": result.tool_call_id,
                    "success": result.success
                }
            ))
        
        return messages
    
    def _format_tool_calls_for_message(self, tool_calls: List[Dict[str, Any]]) -> str:
        """Format tool calls for message content."""
        if not tool_calls:
            return ""
        
        formatted_calls = []
        for tool_call in tool_calls:
            tool_name = tool_call.get('name', 'unknown')
            arguments = tool_call.get('arguments', {})
            
            # Format arguments nicely
            if arguments:
                args_str = json.dumps(arguments, indent=2)
                formatted_calls.append(f"Calling {tool_name} with arguments:\n{args_str}")
            else:
                formatted_calls.append(f"Calling {tool_name} with no arguments")
        
        return "\n\n".join(formatted_calls)
    
    def _format_tool_result_for_message(self, result: ToolResult) -> str:
        """Format tool result for message content."""
        if result.success:
            if isinstance(result.result, dict):
                result_str = json.dumps(result.result, indent=2)
            else:
                result_str = str(result.result)
            
            duration_info = f" (took {result.duration_ms}ms)" if result.duration_ms else ""
            return f"Tool execution successful{duration_info}:\n{result_str}"
        else:
            error_msg = result.error or "Unknown error"
            return f"Tool execution failed: {error_msg}"
    
    def extract_tool_calls_from_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract tool calls from LLM response.
        
        Args:
            response: LLM response dictionary
            
        Returns:
            List of tool call dictionaries
        """
        if response.get('type') == 'tool_calls':
            return response.get('tool_calls', [])
        return []
    
    def should_continue_conversation(
        self,
        response: Dict[str, Any],
        max_iterations: int = 10,
        current_iteration: int = 0
    ) -> bool:
        """Determine if conversation should continue based on response.
        
        Args:
            response: LLM response
            max_iterations: Maximum number of iterations
            current_iteration: Current iteration count
            
        Returns:
            True if conversation should continue
        """
        # Stop if max iterations reached
        if current_iteration >= max_iterations:
            logger.warning(f"Max iterations ({max_iterations}) reached")
            return False
        
        # Continue if there are tool calls to execute
        tool_calls = self.extract_tool_calls_from_response(response)
        return len(tool_calls) > 0
    
    def create_system_message_with_tools(self, base_system_prompt: str) -> Message:
        """Create system message with tool information.
        
        Args:
            base_system_prompt: Base system prompt
            
        Returns:
            System message with tool information
        """
        from agent.llm.schemas import get_system_prompt_with_tools
        
        # If available_tools is specified, we could filter the prompt
        # For now, use the full system prompt
        full_prompt = get_system_prompt_with_tools()
        
        # Combine with base prompt if provided
        if base_system_prompt:
            combined_prompt = f"{base_system_prompt}\n\n{full_prompt}"
        else:
            combined_prompt = full_prompt
        
        return Message(
            role=MessageRole.SYSTEM,
            content=combined_prompt,
            metadata={"available_tools": self.available_tools}
        )
    
    def estimate_tokens_for_tools(self, tool_schemas: List[Dict[str, Any]]) -> int:
        """Estimate token count for tool schemas.
        
        Args:
            tool_schemas: List of tool schemas
            
        Returns:
            Estimated token count
        """
        # Convert schemas to JSON and estimate tokens
        schemas_json = json.dumps(tool_schemas, indent=2)
        # Rough estimate: ~4 characters per token
        return max(1, len(schemas_json) // 4)
    
    def get_tool_usage_stats(self, messages: List[Message]) -> Dict[str, Any]:
        """Get statistics about tool usage in conversation.
        
        Args:
            messages: List of conversation messages
            
        Returns:
            Dictionary with tool usage statistics
        """
        stats = {
            "total_tool_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "tools_used": {},
            "average_duration_ms": 0
        }
        
        total_duration = 0
        duration_count = 0
        
        for message in messages:
            if message.role == MessageRole.ASSISTANT and "tool_calls" in message.metadata:
                tool_calls = message.metadata["tool_calls"]
                stats["total_tool_calls"] += len(tool_calls)
                
                for tool_call in tool_calls:
                    tool_name = tool_call.get("name")
                    if tool_name:
                        stats["tools_used"][tool_name] = stats["tools_used"].get(tool_name, 0) + 1
            
            elif message.role == MessageRole.TOOL:
                if message.metadata.get("success"):
                    stats["successful_calls"] += 1
                else:
                    stats["failed_calls"] += 1
                
                # Track duration if available
                if "duration_ms" in message.metadata:
                    total_duration += message.metadata["duration_ms"]
                    duration_count += 1
        
        if duration_count > 0:
            stats["average_duration_ms"] = total_duration / duration_count
        
        return stats


def create_tool_error_message(tool_call_id: str, error: str) -> Message:
    """Create a tool error message.
    
    Args:
        tool_call_id: ID of the failed tool call
        error: Error message
        
    Returns:
        Tool message with error information
    """
    return Message(
        role=MessageRole.TOOL,
        content=f"Tool execution failed: {error}",
        metadata={
            "tool_call_id": tool_call_id,
            "success": False,
            "error": error
        }
    )


def create_tool_success_message(
    tool_call_id: str,
    result: Any,
    duration_ms: Optional[int] = None
) -> Message:
    """Create a tool success message.
    
    Args:
        tool_call_id: ID of the successful tool call
        result: Tool execution result
        duration_ms: Execution duration in milliseconds
        
    Returns:
        Tool message with success information
    """
    if isinstance(result, dict):
        content = json.dumps(result, indent=2)
    else:
        content = str(result)
    
    metadata = {
        "tool_call_id": tool_call_id,
        "success": True,
        "result": result
    }
    
    if duration_ms is not None:
        metadata["duration_ms"] = duration_ms
        content = f"Tool execution successful (took {duration_ms}ms):\n{content}"
    else:
        content = f"Tool execution successful:\n{content}"
    
    return Message(
        role=MessageRole.TOOL,
        content=content,
        metadata=metadata
    )