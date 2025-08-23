"""Main agent orchestrator implementing ReAct loop and coordination."""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Union

from agent.config import get_settings
from agent.llm.bedrock_client import BedrockClient
from agent.memory.provider import MemoryProvider
from agent.orchestrator.executor import TaskExecutor
from agent.orchestrator.planner import TaskPlanner
from agent.orchestrator.state import ExecutionState, ExecutionStatus, ExecutionStep

logger = logging.getLogger(__name__)


class AgentOrchestratorError(Exception):
    """Exception for agent orchestrator operations."""
    pass


class StreamingEvent:
    """Event for streaming updates."""
    
    def __init__(self, event_type: str, data: Any, timestamp: Optional[str] = None):
        self.event_type = event_type
        self.data = data
        self.timestamp = timestamp or str(asyncio.get_event_loop().time())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp,
        }


class AgentOrchestrator:
    """Main orchestrator implementing ReAct (Reasoning and Acting) loop."""
    
    def __init__(
        self,
        bedrock_client: Optional[BedrockClient] = None,
        memory_provider: Optional[MemoryProvider] = None,
        workspace_root: Optional[str] = None,
    ):
        """Initialize agent orchestrator.
        
        Args:
            bedrock_client: Bedrock client for LLM operations
            memory_provider: Memory provider for context and learning
            workspace_root: Root directory for workspace operations
        """
        self.bedrock = bedrock_client or BedrockClient()
        self.memory_provider = memory_provider
        self.settings = get_settings()
        
        # Initialize components
        self.planner = TaskPlanner(
            bedrock_client=self.bedrock,
            memory_provider=self.memory_provider
        )
        
        self.executor = TaskExecutor(
            bedrock_client=self.bedrock,
            memory_provider=self.memory_provider,
            workspace_root=workspace_root
        )
        
        # Active executions
        self.active_executions: Dict[str, ExecutionState] = {}
        
        # Streaming callbacks
        self.streaming_callbacks: List[Callable[[StreamingEvent], None]] = []
        
        # Setup executor callbacks for streaming
        self.executor.add_step_callback("started", self._on_step_started)
        self.executor.add_step_callback("completed", self._on_step_completed)
        self.executor.add_step_callback("failed", self._on_step_failed)
        
        logger.info("Initialized AgentOrchestrator")
    
    def add_streaming_callback(self, callback: Callable[[StreamingEvent], None]):
        """Add callback for streaming events.
        
        Args:
            callback: Callback function that receives StreamingEvent
        """
        self.streaming_callbacks.append(callback)
    
    def _emit_streaming_event(self, event_type: str, data: Any):
        """Emit streaming event to all callbacks.
        
        Args:
            event_type: Type of event
            data: Event data
        """
        event = StreamingEvent(event_type, data)
        for callback in self.streaming_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Streaming callback error: {e}")
    
    def _on_step_started(self, step: ExecutionStep):
        """Handle step started event."""
        self._emit_streaming_event("step_started", {
            "step_id": step.id,
            "description": step.description,
            "tool_name": step.tool_name,
            "step_type": step.step_type.value,
        })
    
    def _on_step_completed(self, step: ExecutionStep):
        """Handle step completed event."""
        self._emit_streaming_event("step_completed", {
            "step_id": step.id,
            "description": step.description,
            "result": str(step.result)[:500] if step.result else None,  # Truncate long results
            "status": step.status.value,
        })
    
    def _on_step_failed(self, step: ExecutionStep, error: str):
        """Handle step failed event."""
        self._emit_streaming_event("step_failed", {
            "step_id": step.id,
            "description": step.description,
            "error": error,
            "status": step.status.value,
        })
    
    async def execute_instruction(
        self,
        instruction: str,
        context: Optional[Dict[str, Any]] = None,
        streaming: bool = False,
        max_retries: int = 3,
        continue_on_error: bool = False,
        max_react_iterations: int = 5
    ) -> Union[ExecutionState, AsyncGenerator[StreamingEvent, None]]:
        """Execute an instruction using ReAct loop.
        
        Args:
            instruction: The instruction to execute
            context: Additional context information
            streaming: Whether to return streaming generator
            max_retries: Maximum retries per step
            continue_on_error: Whether to continue on step failures
            max_react_iterations: Maximum ReAct loop iterations
            
        Returns:
            ExecutionState or AsyncGenerator of StreamingEvent
        """
        logger.info(f"Executing instruction: {instruction[:100]}...")
        
        if streaming:
            return self._execute_instruction_streaming(
                instruction=instruction,
                context=context,
                max_retries=max_retries,
                continue_on_error=continue_on_error,
                max_react_iterations=max_react_iterations
            )
        else:
            return await self._execute_instruction_sync(
                instruction=instruction,
                context=context,
                max_retries=max_retries,
                continue_on_error=continue_on_error,
                max_react_iterations=max_react_iterations
            )
    
    async def _execute_instruction_sync(
        self,
        instruction: str,
        context: Optional[Dict[str, Any]],
        max_retries: int,
        continue_on_error: bool,
        max_react_iterations: int
    ) -> ExecutionState:
        """Execute instruction synchronously."""
        
        try:
            # Create initial plan
            self._emit_streaming_event("planning_started", {"instruction": instruction})
            
            execution_state = await self.planner.create_plan(
                instruction=instruction,
                context=context,
                available_tools=self.executor.get_available_tools()
            )
            
            self.active_executions[execution_state.id] = execution_state
            
            self._emit_streaming_event("planning_completed", {
                "execution_id": execution_state.id,
                "plan": execution_state.plan,
                "total_steps": len(execution_state.steps)
            })
            
            # Execute with ReAct loop
            execution_state = await self._react_loop(
                execution_state=execution_state,
                max_retries=max_retries,
                continue_on_error=continue_on_error,
                max_iterations=max_react_iterations
            )
            
            # Store execution result in memory if available
            if self.memory_provider and execution_state.status == ExecutionStatus.COMPLETED:
                await self._store_execution_memory(execution_state)
            
            return execution_state
            
        except Exception as e:
            logger.error(f"Instruction execution failed: {e}")
            self._emit_streaming_event("execution_error", {"error": str(e)})
            raise AgentOrchestratorError(f"Execution failed: {e}") from e
        
        finally:
            # Clean up active execution
            if execution_state.id in self.active_executions:
                del self.active_executions[execution_state.id]
    
    async def _execute_instruction_streaming(
        self,
        instruction: str,
        context: Optional[Dict[str, Any]],
        max_retries: int,
        continue_on_error: bool,
        max_react_iterations: int
    ) -> AsyncGenerator[StreamingEvent, None]:
        """Execute instruction with streaming updates."""
        
        # Create a queue for streaming events
        event_queue = asyncio.Queue()
        
        def queue_callback(event: StreamingEvent):
            try:
                event_queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Streaming event queue full, dropping event")
        
        # Add temporary callback
        self.add_streaming_callback(queue_callback)
        
        try:
            # Start execution in background
            execution_task = asyncio.create_task(
                self._execute_instruction_sync(
                    instruction=instruction,
                    context=context,
                    max_retries=max_retries,
                    continue_on_error=continue_on_error,
                    max_react_iterations=max_react_iterations
                )
            )
            
            # Yield events as they come
            while not execution_task.done():
                try:
                    # Wait for event with timeout
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                    yield event
                except asyncio.TimeoutError:
                    continue
            
            # Yield any remaining events
            while not event_queue.empty():
                try:
                    event = event_queue.get_nowait()
                    yield event
                except asyncio.QueueEmpty:
                    break
            
            # Get final result and yield completion event
            try:
                final_state = await execution_task
                yield StreamingEvent("execution_completed", {
                    "execution_id": final_state.id,
                    "status": final_state.status.value,
                    "total_steps": len(final_state.steps),
                    "completed_steps": len([s for s in final_state.steps if s.status == ExecutionStatus.COMPLETED])
                })
            except Exception as e:
                yield StreamingEvent("execution_error", {"error": str(e)})
                raise
        
        finally:
            # Remove temporary callback
            if queue_callback in self.streaming_callbacks:
                self.streaming_callbacks.remove(queue_callback)
    
    async def _react_loop(
        self,
        execution_state: ExecutionState,
        max_retries: int,
        continue_on_error: bool,
        max_iterations: int
    ) -> ExecutionState:
        """Execute ReAct (Reasoning and Acting) loop.
        
        Args:
            execution_state: Current execution state
            max_retries: Maximum retries per step
            continue_on_error: Whether to continue on errors
            max_iterations: Maximum loop iterations
            
        Returns:
            Updated execution state
        """
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            self._emit_streaming_event("react_iteration_started", {
                "iteration": iteration,
                "execution_id": execution_state.id
            })
            
            # Execute current plan
            execution_state = await self.executor.execute(
                execution_state=execution_state,
                max_retries=max_retries,
                continue_on_error=continue_on_error
            )
            
            # Check if execution completed successfully
            if execution_state.status == ExecutionStatus.COMPLETED:
                self._emit_streaming_event("react_loop_completed", {
                    "execution_id": execution_state.id,
                    "iterations": iteration,
                    "status": "completed"
                })
                break
            
            # If execution failed, try to reason about the failure and replan
            if execution_state.status == ExecutionStatus.FAILED:
                logger.info(f"Execution failed, attempting to replan (iteration {iteration})")
                
                # Get failure analysis
                failure_analysis = await self._analyze_failure(execution_state)
                
                self._emit_streaming_event("failure_analysis", {
                    "execution_id": execution_state.id,
                    "analysis": failure_analysis,
                    "iteration": iteration
                })
                
                # Try to refine the plan
                try:
                    execution_state = await self.planner.refine_plan(
                        execution_state=execution_state,
                        feedback=failure_analysis
                    )
                    
                    # Reset status to continue execution
                    execution_state.status = ExecutionStatus.RUNNING
                    
                    self._emit_streaming_event("plan_refined", {
                        "execution_id": execution_state.id,
                        "new_plan": execution_state.plan,
                        "iteration": iteration
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to refine plan: {e}")
                    self._emit_streaming_event("refinement_failed", {
                        "execution_id": execution_state.id,
                        "error": str(e),
                        "iteration": iteration
                    })
                    break
            
            # If we're paused or cancelled, break
            if execution_state.status in [ExecutionStatus.PAUSED, ExecutionStatus.CANCELLED]:
                break
        
        # If we exhausted iterations without success
        if iteration >= max_iterations and execution_state.status not in [
            ExecutionStatus.COMPLETED, ExecutionStatus.CANCELLED
        ]:
            execution_state.fail(f"Maximum ReAct iterations ({max_iterations}) exceeded")
            self._emit_streaming_event("react_loop_exhausted", {
                "execution_id": execution_state.id,
                "max_iterations": max_iterations
            })
        
        return execution_state
    
    async def _analyze_failure(self, execution_state: ExecutionState) -> str:
        """Analyze execution failure to provide feedback for replanning.
        
        Args:
            execution_state: Failed execution state
            
        Returns:
            Failure analysis text
        """
        # Get failed steps
        failed_steps = [step for step in execution_state.steps if step.status == ExecutionStatus.FAILED]
        
        if not failed_steps:
            return "Execution failed but no specific step failures found"
        
        # Create context for analysis
        failure_context = {
            "instruction": execution_state.instruction,
            "failed_steps": [
                {
                    "description": step.description,
                    "tool_name": step.tool_name,
                    "error": step.error,
                    "tool_args": step.tool_args
                }
                for step in failed_steps
            ],
            "completed_steps": [
                {
                    "description": step.description,
                    "result": str(step.result)[:200] if step.result else None
                }
                for step in execution_state.steps
                if step.status == ExecutionStatus.COMPLETED
            ]
        }
        
        system_prompt = """You are an AI agent analyzing execution failures to provide feedback for replanning.

Your task is to:
1. Analyze what went wrong in the execution
2. Identify the root cause of failures
3. Suggest how the plan should be modified
4. Consider alternative approaches

Be specific about what failed and provide actionable feedback for replanning."""
        
        user_message = f"""Please analyze the following execution failure:

Original instruction: {execution_state.instruction}

Failed steps:
{json.dumps(failure_context['failed_steps'], indent=2)}

Completed steps:
{json.dumps(failure_context['completed_steps'], indent=2)}

Please provide analysis of what went wrong and suggestions for how to modify the plan to succeed."""
        
        try:
            # Convert to Message objects
            from agent.models.base import Message
            messages = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=user_message)
            ]
            
            response_data = await self.bedrock.chat_with_tools(
                messages=messages,
                max_tokens=2000,
                temperature=0.3,
            )
            
            # Extract text content from response
            if isinstance(response_data, dict) and "content" in response_data:
                analysis = response_data["content"]
            else:
                analysis = str(response_data)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failure analysis failed: {e}")
            return f"Failed to analyze execution failure: {str(e)}"
    
    async def _store_execution_memory(self, execution_state: ExecutionState):
        """Store successful execution in memory for future reference.
        
        Args:
            execution_state: Completed execution state
        """
        if not self.memory_provider:
            return
        
        try:
            # Create memory content
            memory_content = f"Successfully executed: {execution_state.instruction}\n\n"
            memory_content += f"Plan used:\n"
            for i, step_desc in enumerate(execution_state.plan, 1):
                memory_content += f"{i}. {step_desc}\n"
            
            memory_content += f"\nExecution completed in {len(execution_state.steps)} steps"
            
            # Calculate importance based on complexity and success
            importance = min(0.9, 0.5 + (len(execution_state.steps) * 0.05))
            
            # Store in memory
            await self.memory_provider.add_project_memory(
                content=memory_content,
                summary=f"Successful execution: {execution_state.instruction[:100]}",
                tags=["execution", "success", "plan"],
                importance=importance,
                metadata={
                    "execution_id": execution_state.id,
                    "step_count": len(execution_state.steps),
                    "tools_used": list(set(
                        step.tool_name for step in execution_state.steps
                        if step.tool_name
                    )),
                }
            )
            
            logger.info(f"Stored execution memory for: {execution_state.instruction[:50]}...")
            
        except Exception as e:
            logger.error(f"Failed to store execution memory: {e}")
    
    async def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get status of an active execution.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            Execution status information or None if not found
        """
        if execution_id not in self.active_executions:
            return None
        
        execution_state = self.active_executions[execution_id]
        progress = execution_state.get_progress()
        
        return {
            "execution_id": execution_id,
            "instruction": execution_state.instruction,
            "status": execution_state.status.value,
            "progress": progress,
            "current_step": execution_state.get_current_step().description if execution_state.get_current_step() else None,
            "created_at": execution_state.created_at.isoformat(),
            "started_at": execution_state.started_at.isoformat() if execution_state.started_at else None,
        }
    
    async def pause_execution(self, execution_id: str) -> bool:
        """Pause an active execution.
        
        Args:
            execution_id: Execution ID to pause
            
        Returns:
            True if paused successfully
        """
        if execution_id not in self.active_executions:
            return False
        
        execution_state = self.active_executions[execution_id]
        await self.executor.pause_execution(execution_state)
        
        self._emit_streaming_event("execution_paused", {
            "execution_id": execution_id
        })
        
        return True
    
    async def resume_execution(self, execution_id: str) -> bool:
        """Resume a paused execution.
        
        Args:
            execution_id: Execution ID to resume
            
        Returns:
            True if resumed successfully
        """
        if execution_id not in self.active_executions:
            return False
        
        execution_state = self.active_executions[execution_id]
        
        if execution_state.status != ExecutionStatus.PAUSED:
            return False
        
        self._emit_streaming_event("execution_resumed", {
            "execution_id": execution_id
        })
        
        # Resume execution in background
        asyncio.create_task(self.executor.resume_execution(execution_state))
        
        return True
    
    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel an active execution.
        
        Args:
            execution_id: Execution ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        if execution_id not in self.active_executions:
            return False
        
        execution_state = self.active_executions[execution_id]
        await self.executor.cancel_execution(execution_state)
        
        self._emit_streaming_event("execution_cancelled", {
            "execution_id": execution_id
        })
        
        return True
    
    def get_active_executions(self) -> List[str]:
        """Get list of active execution IDs.
        
        Returns:
            List of execution IDs
        """
        return list(self.active_executions.keys())