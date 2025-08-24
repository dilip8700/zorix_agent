"""ReAct / Plan-Act loop + tool wiring for LLM orchestration."""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from agent.config import get_settings
from agent.llm.bedrock_client import BedrockClient
from agent.llm.schemas import get_all_tool_schemas, get_system_prompt_with_tools
from agent.llm.tool_calling import validate_tool_call, execute_tool_call
from agent.memory.provider import MemoryProvider
from agent.models.base import Message, MessageRole, ToolCall, ToolResult

logger = logging.getLogger(__name__)


class LLMOrchestrator:
    """Implements ReAct / Plan-Act loop with tool calling."""
    
    def __init__(
        self,
        bedrock_client: BedrockClient,
        memory_provider: Optional[MemoryProvider] = None,
        workspace_root: Optional[str] = None,
    ):
        """Initialize LLM orchestrator.
        
        Args:
            bedrock_client: Bedrock client for LLM operations
            memory_provider: Memory provider for context
            workspace_root: Root directory for workspace operations
        """
        self.bedrock = bedrock_client
        self.memory_provider = memory_provider
        self.settings = get_settings()
        self.workspace_root = workspace_root or self.settings.workspace_root
        
        # Get available tools and schemas
        self.tool_schemas = get_all_tool_schemas()
        self.system_prompt = get_system_prompt_with_tools()
        
        logger.info("Initialized LLMOrchestrator")
    
    async def chat_with_tools(
        self,
        messages: List[Message],
        mode: str = "create",
        tools_allow: Optional[List[str]] = None,
        max_iterations: int = 10,
        stream: bool = False
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Chat with LLM using ReAct loop and tool calling.
        
        Args:
            messages: Conversation messages
            mode: Chat mode (explain|edit|create|review)
            tools_allow: Allowed tool names (None = all)
            max_iterations: Maximum ReAct iterations
            stream: Whether to stream responses
            
        Yields:
            Response chunks or tool execution updates
        """
        logger.info(f"Starting chat with tools in {mode} mode")
        
        # Filter available tools
        available_schemas = self.tool_schemas
        if tools_allow:
            available_schemas = [
                schema for schema in self.tool_schemas
                if schema["name"] in tools_allow
            ]
        
        # Build conversation with system prompt
        conversation = [
            Message(role=MessageRole.SYSTEM, content=self.system_prompt)
        ]
        conversation.extend(messages)
        
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            
            try:
                # Get LLM response
                if stream:
                    yield {"type": "thinking", "iteration": iteration}
                
                response = await self.bedrock.chat_with_tools(
                    messages=conversation,
                    tool_schemas=available_schemas,
                    max_tokens=self.settings.max_tokens,
                    temperature=self.settings.temperature,
                )
                
                # Check if response contains tool calls
                if isinstance(response, dict) and "tool_calls" in response:
                    tool_calls = response["tool_calls"]
                    
                    if stream:
                        yield {
                            "type": "tool_calls_start",
                            "tool_calls": [
                                {"name": tc.get("name"), "id": tc.get("id")}
                                for tc in tool_calls
                            ]
                        }
                    
                    # Execute tool calls
                    tool_results = []
                    for tool_call in tool_calls:
                        try:
                            # Validate tool call
                            if not validate_tool_call(tool_call["name"], tool_call.get("arguments", {})):
                                raise ValueError(f"Invalid tool call: {tool_call['name']}")
                            
                            if stream:
                                yield {
                                    "type": "tool_call_start",
                                    "tool_name": tool_call["name"],
                                    "tool_args": tool_call.get("arguments", {})
                                }
                            
                            # Execute tool
                            result = await execute_tool_call(
                                tool_name=tool_call["name"],
                                arguments=tool_call.get("arguments", {}),
                                workspace_root=self.workspace_root
                            )
                            
                            tool_results.append(ToolResult(
                                tool_call_id=tool_call.get("id", ""),
                                success=True,
                                result=result
                            ))
                            
                            if stream:
                                yield {
                                    "type": "tool_call_result",
                                    "tool_name": tool_call["name"],
                                    "success": True,
                                    "result": result
                                }
                                
                        except Exception as e:
                            logger.error(f"Tool execution failed: {e}")
                            tool_results.append(ToolResult(
                                tool_call_id=tool_call.get("id", ""),
                                success=False,
                                error=str(e)
                            ))
                            
                            if stream:
                                yield {
                                    "type": "tool_call_result",
                                    "tool_name": tool_call["name"],
                                    "success": False,
                                    "error": str(e)
                                }
                    
                    # Add tool results to conversation
                    for result in tool_results:
                        if result.success:
                            observation = f"Tool {tool_call['name']} executed successfully. Result: {result.result}"
                        else:
                            observation = f"Tool {tool_call['name']} failed. Error: {result.error}"
                        
                        conversation.append(Message(
                            role=MessageRole.TOOL,
                            content=observation
                        ))
                    
                    # Continue the loop for next iteration
                    continue
                
                else:
                    # Final response without tool calls
                    content = response.get("content", str(response)) if isinstance(response, dict) else str(response)
                    
                    if stream:
                        # Stream the final response
                        for chunk in content.split():
                            yield {
                                "type": "message_delta",
                                "content": chunk + " "
                            }
                    
                    yield {
                        "type": "message_complete",
                        "content": content,
                        "iteration": iteration
                    }
                    
                    # Store conversation in memory if available
                    if self.memory_provider:
                        try:
                            await self.memory_provider.store_conversation_turn(
                                session_id="default",
                                user_message=messages[-1].content if messages else "",
                                assistant_response=content,
                                context={"mode": mode, "iteration": iteration}
                            )
                        except Exception as e:
                            logger.warning(f"Failed to store conversation: {e}")
                    
                    break
                    
            except Exception as e:
                logger.error(f"Chat iteration {iteration} failed: {e}")
                yield {
                    "type": "error",
                    "error": str(e),
                    "iteration": iteration
                }
                break
        
        if iteration >= max_iterations:
            yield {
                "type": "max_iterations_reached",
                "message": f"Reached maximum iterations ({max_iterations})"
            }
    
    async def plan_task(
        self,
        instruction: str,
        context: Optional[Dict[str, Any]] = None,
        mode: str = "edit"
    ) -> Dict[str, Any]:
        """Create a plan for a task using LLM.
        
        Args:
            instruction: Task instruction
            context: Additional context
            mode: Planning mode
            
        Returns:
            Plan with steps and metadata
        """
        logger.info(f"Planning task: {instruction[:100]}...")
        
        # Get relevant context from memory and vector search
        memory_context = ""
        if self.memory_provider:
            try:
                memories = await self.memory_provider.search_memories(
                    query=instruction,
                    max_results=3
                )
                if memories:
                    memory_context = "\n".join([
                        f"- {mem.entry.summary}: {mem.entry.content[:100]}..."
                        for mem in memories
                    ])
            except Exception as e:
                logger.warning(f"Failed to get memory context: {e}")
        
        # Create planning prompt
        planning_prompt = f"""
        Please analyze this task and create a detailed execution plan:
        
        Task: {instruction}
        Mode: {mode}
        
        Context from memory:
        {memory_context}
        
        Additional context:
        {json.dumps(context or {}, indent=2)}
        
        Create a step-by-step plan that uses the available tools to complete this task.
        Consider the mode ({mode}) when planning the approach.
        
        For each step, specify:
        1. What tool to use
        2. What arguments to pass
        3. Why this step is needed
        4. What the expected outcome is
        
        Respond with a structured plan.
        """
        
        messages = [Message(role=MessageRole.USER, content=planning_prompt)]
        
        # Get plan from LLM
        response = await self.bedrock.chat_with_tools(
            messages=[Message(role=MessageRole.SYSTEM, content=self.system_prompt)] + messages,
            tool_schemas=self.tool_schemas,
            max_tokens=3000,
            temperature=0.1  # Low temperature for consistent planning
        )
        
        # Extract plan from response
        plan_content = response.get("content", str(response)) if isinstance(response, dict) else str(response)
        
        return {
            "instruction": instruction,
            "mode": mode,
            "plan_content": plan_content,
            "context": context,
            "memory_context": memory_context,
            "available_tools": [schema["name"] for schema in self.tool_schemas]
        }
    
    async def get_memory_context(self, query: str, max_results: int = 5) -> str:
        """Get relevant context from memory.
        
        Args:
            query: Search query
            max_results: Maximum results to return
            
        Returns:
            Formatted memory context
        """
        if not self.memory_provider:
            return ""
        
        try:
            memories = await self.memory_provider.search_memories(
                query=query,
                max_results=max_results
            )
            
            if not memories:
                return ""
            
            context_parts = []
            for mem in memories:
                context_parts.append(f"- {mem.entry.summary}: {mem.entry.content[:200]}...")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.warning(f"Failed to get memory context: {e}")
            return ""
