"""Task execution engine for running planned steps."""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Union

from agent.config import get_settings
from agent.llm.bedrock_client import BedrockClient
from agent.memory.provider import MemoryProvider
from agent.orchestrator.state import ExecutionState, ExecutionStatus, ExecutionStep, StepType
from agent.tools.command import CommandTools
from agent.tools.filesystem import FilesystemTools
from agent.tools.git import GitTools

logger = logging.getLogger(__name__)


class TaskExecutorError(Exception):
    """Exception for task execution operations."""
    pass


class TaskExecutor:
    """Executes planned tasks with proper error handling and validation."""
    
    def __init__(
        self,
        bedrock_client: Optional[BedrockClient] = None,
        memory_provider: Optional[MemoryProvider] = None,
        workspace_root: Optional[str] = None,
    ):
        """Initialize task executor.
        
        Args:
            bedrock_client: Bedrock client for LLM operations
            memory_provider: Memory provider for context
            workspace_root: Root directory for workspace operations
        """
        self.bedrock = bedrock_client or BedrockClient()
        self.memory_provider = memory_provider
        self.settings = get_settings()
        
        # Initialize tools
        self.filesystem_tools = FilesystemTools(workspace_root=workspace_root)
        self.command_tools = CommandTools(workspace_root=workspace_root)
        self.git_tools = GitTools(workspace_root=workspace_root)
        
        # Tool registry
        self.tools = {
            "read_file": self.filesystem_tools.read_file,
            "write_file": self.filesystem_tools.write_file,
            "list_directory": self.filesystem_tools.list_directory,
            "apply_patch": self.filesystem_tools.apply_patch,
            "run_command": self.command_tools.run_command,
            "git_status": self.git_tools.git_status,
            "git_diff": self.git_tools.git_diff,
            "git_add": self.git_tools.git_add,
            "git_commit": self.git_tools.git_commit,
            "git_branch": self.git_tools.git_branch,
            "git_log": self.git_tools.git_log,
            "git_reset": self.git_tools.git_reset,
        }
        
        # Execution callbacks
        self.step_started_callbacks: List[Callable[[ExecutionStep], None]] = []
        self.step_completed_callbacks: List[Callable[[ExecutionStep], None]] = []
        self.step_failed_callbacks: List[Callable[[ExecutionStep, str], None]] = []
        
        logger.info("Initialized TaskExecutor")
    
    def add_tool(self, name: str, tool_func: Callable):
        """Add a custom tool to the executor.
        
        Args:
            name: Tool name
            tool_func: Tool function
        """
        self.tools[name] = tool_func
        logger.info(f"Added tool: {name}")
    
    def add_step_callback(
        self,
        event: str,
        callback: Callable
    ):
        """Add callback for step events.
        
        Args:
            event: Event type ('started', 'completed', 'failed')
            callback: Callback function
        """
        if event == "started":
            self.step_started_callbacks.append(callback)
        elif event == "completed":
            self.step_completed_callbacks.append(callback)
        elif event == "failed":
            self.step_failed_callbacks.append(callback)
        else:
            raise ValueError(f"Unknown event type: {event}")
    
    async def execute(
        self,
        execution_state: ExecutionState,
        start_from_step: Optional[int] = None,
        max_retries: int = 3,
        continue_on_error: bool = False
    ) -> ExecutionState:
        """Execute the planned steps.
        
        Args:
            execution_state: Execution state with planned steps
            start_from_step: Step index to start from (default: current step)
            max_retries: Maximum retries per step
            continue_on_error: Whether to continue execution after step failures
            
        Returns:
            Updated execution state
        """
        logger.info(f"Starting execution of {len(execution_state.steps)} steps")
        
        if execution_state.status == ExecutionStatus.PENDING:
            execution_state.start()
        elif execution_state.status == ExecutionStatus.PAUSED:
            execution_state.resume()
        
        # Determine starting step
        start_step = start_from_step if start_from_step is not None else execution_state.current_step_index
        
        try:
            for i in range(start_step, len(execution_state.steps)):
                execution_state.current_step_index = i
                step = execution_state.steps[i]
                
                # Skip already completed steps
                if step.status == ExecutionStatus.COMPLETED:
                    continue
                
                # Execute step with retries
                success = await self._execute_step_with_retries(
                    step=step,
                    execution_state=execution_state,
                    max_retries=max_retries
                )
                
                if not success:
                    if continue_on_error:
                        logger.warning(f"Step {i+1} failed, continuing due to continue_on_error=True")
                        continue
                    else:
                        logger.error(f"Step {i+1} failed, stopping execution")
                        execution_state.fail(f"Step {i+1} failed: {step.error}")
                        return execution_state
                
                # Create rollback point after successful steps
                if step.status == ExecutionStatus.COMPLETED:
                    execution_state.create_rollback_point(f"After step {i+1}: {step.description}")
            
            # All steps completed successfully
            execution_state.complete()
            logger.info("Execution completed successfully")
            
        except Exception as e:
            logger.error(f"Execution failed with exception: {e}")
            execution_state.fail(f"Execution exception: {str(e)}")
            raise TaskExecutorError(f"Execution failed: {e}") from e
        
        return execution_state
    
    async def _execute_step_with_retries(
        self,
        step: ExecutionStep,
        execution_state: ExecutionState,
        max_retries: int
    ) -> bool:
        """Execute a single step with retry logic.
        
        Args:
            step: Step to execute
            execution_state: Current execution state
            max_retries: Maximum number of retries
            
        Returns:
            True if step succeeded, False otherwise
        """
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Executing step: {step.description} (attempt {attempt + 1})")
                
                # Start step
                step.start()
                for callback in self.step_started_callbacks:
                    callback(step)
                
                # Execute based on step type
                if step.step_type == StepType.TOOL_CALL:
                    result = await self._execute_tool_call(step, execution_state)
                elif step.step_type == StepType.REASONING:
                    result = await self._execute_reasoning(step, execution_state)
                elif step.step_type == StepType.VALIDATION:
                    result = await self._execute_validation(step, execution_state)
                else:
                    result = f"Executed {step.step_type.value} step"
                
                # Complete step
                step.complete(result)
                for callback in self.step_completed_callbacks:
                    callback(step)
                
                logger.info(f"Step completed successfully: {step.description}")
                return True
                
            except Exception as e:
                error_msg = f"Step execution failed (attempt {attempt + 1}): {str(e)}"
                logger.error(error_msg)
                
                if attempt == max_retries:
                    # Final failure
                    step.fail(error_msg)
                    for callback in self.step_failed_callbacks:
                        callback(step, error_msg)
                    return False
                else:
                    # Retry after delay
                    await asyncio.sleep(1.0 * (attempt + 1))  # Exponential backoff
        
        return False
    
    async def _execute_tool_call(
        self,
        step: ExecutionStep,
        execution_state: ExecutionState
    ) -> Any:
        """Execute a tool call step.
        
        Args:
            step: Step with tool call information
            execution_state: Current execution state
            
        Returns:
            Tool execution result
        """
        if not step.tool_name:
            raise TaskExecutorError("Tool call step missing tool name")
        
        if step.tool_name not in self.tools:
            raise TaskExecutorError(f"Unknown tool: {step.tool_name}")
        
        tool_func = self.tools[step.tool_name]
        tool_args = step.tool_args or {}
        
        logger.debug(f"Calling tool {step.tool_name} with args: {tool_args}")
        
        try:
            # Call the tool
            if asyncio.iscoroutinefunction(tool_func):
                result = await tool_func(**tool_args)
            else:
                result = tool_func(**tool_args)
            
            # Store result in execution context
            execution_state.context[f"step_{step.id}_result"] = result
            
            return result
            
        except Exception as e:
            raise TaskExecutorError(f"Tool {step.tool_name} failed: {str(e)}") from e
    
    async def _execute_reasoning(
        self,
        step: ExecutionStep,
        execution_state: ExecutionState
    ) -> str:
        """Execute a reasoning step using LLM.
        
        Args:
            step: Reasoning step
            execution_state: Current execution state
            
        Returns:
            Reasoning result
        """
        # Create context for reasoning
        context = {
            "instruction": execution_state.instruction,
            "step_description": step.description,
            "execution_context": execution_state.context,
            "previous_steps": [
                {
                    "description": s.description,
                    "result": s.result,
                    "status": s.status.value
                }
                for s in execution_state.steps[:execution_state.current_step_index]
            ]
        }
        
        system_prompt = """You are an AI agent performing a reasoning step in a larger execution plan.

Your task is to:
1. Analyze the current situation based on the context
2. Provide insights, decisions, or analysis as requested
3. Consider the results of previous steps
4. Provide clear, actionable reasoning

Be concise but thorough in your reasoning."""
        
        user_message = f"""Please perform the following reasoning step:

{step.description}

Context:
- Original instruction: {execution_state.instruction}
- Previous steps and results: {context['previous_steps']}
- Current execution context: {execution_state.context}

Please provide your reasoning and any conclusions."""
        
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
                response = response_data["content"]
            else:
                response = str(response_data)
            
            # Store reasoning result in context
            execution_state.context[f"step_{step.id}_reasoning"] = response
            
            return response
            
        except Exception as e:
            raise TaskExecutorError(f"Reasoning step failed: {str(e)}") from e
    
    async def _execute_validation(
        self,
        step: ExecutionStep,
        execution_state: ExecutionState
    ) -> str:
        """Execute a validation step.
        
        Args:
            step: Validation step
            execution_state: Current execution state
            
        Returns:
            Validation result
        """
        # Get validation criteria from step metadata
        validation_criteria = step.metadata.get("validation_criteria", [])
        
        if not validation_criteria:
            # Generic validation based on step description
            return await self._generic_validation(step, execution_state)
        
        # Specific validation
        validation_results = []
        
        for criterion in validation_criteria:
            try:
                # This could be extended to support different validation types
                result = await self._validate_criterion(criterion, execution_state)
                validation_results.append({
                    "criterion": criterion,
                    "result": result,
                    "passed": True
                })
            except Exception as e:
                validation_results.append({
                    "criterion": criterion,
                    "error": str(e),
                    "passed": False
                })
        
        # Check if all validations passed
        all_passed = all(result["passed"] for result in validation_results)
        
        if not all_passed:
            failed_criteria = [r["criterion"] for r in validation_results if not r["passed"]]
            raise TaskExecutorError(f"Validation failed for criteria: {failed_criteria}")
        
        return f"Validation passed for {len(validation_results)} criteria"
    
    async def _generic_validation(
        self,
        step: ExecutionStep,
        execution_state: ExecutionState
    ) -> str:
        """Perform generic validation using LLM.
        
        Args:
            step: Validation step
            execution_state: Current execution state
            
        Returns:
            Validation result
        """
        system_prompt = """You are an AI agent performing validation in an execution plan.

Your task is to:
1. Analyze the current state and previous step results
2. Validate that the execution is proceeding correctly
3. Check for any issues or problems
4. Provide a clear validation result

If validation fails, explain what went wrong and what needs to be fixed."""
        
        user_message = f"""Please validate the current execution state:

Validation task: {step.description}

Original instruction: {execution_state.instruction}

Previous steps and results:
{[{"desc": s.description, "result": s.result, "status": s.status.value} for s in execution_state.steps[:execution_state.current_step_index]]}

Current context: {execution_state.context}

Please validate that everything is proceeding correctly and report any issues."""
        
        try:
            # Convert to Message objects
            from agent.models.base import Message
            messages = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=user_message)
            ]
            
            response_data = await self.bedrock.chat_with_tools(
                messages=messages,
                max_tokens=1500,
                temperature=0.1,
            )
            
            # Extract text content from response
            if isinstance(response_data, dict) and "content" in response_data:
                response = response_data["content"]
            else:
                response = str(response_data)
            
            # Simple check for validation failure keywords
            failure_keywords = ["fail", "error", "problem", "issue", "wrong", "incorrect"]
            if any(keyword in response.lower() for keyword in failure_keywords):
                raise TaskExecutorError(f"Validation failed: {response}")
            
            return response
            
        except TaskExecutorError:
            raise
        except Exception as e:
            raise TaskExecutorError(f"Validation step failed: {str(e)}") from e
    
    async def _validate_criterion(
        self,
        criterion: str,
        execution_state: ExecutionState
    ) -> bool:
        """Validate a specific criterion.
        
        Args:
            criterion: Validation criterion
            execution_state: Current execution state
            
        Returns:
            True if criterion is met
        """
        # This is a placeholder for specific validation logic
        # In a real implementation, this would check specific conditions
        # based on the criterion type
        
        logger.debug(f"Validating criterion: {criterion}")
        
        # For now, just return True
        # This could be extended to support file existence checks,
        # command output validation, etc.
        return True
    
    async def pause_execution(self, execution_state: ExecutionState):
        """Pause the current execution.
        
        Args:
            execution_state: Execution state to pause
        """
        execution_state.pause()
        logger.info("Execution paused")
    
    async def resume_execution(
        self,
        execution_state: ExecutionState,
        max_retries: int = 3,
        continue_on_error: bool = False
    ) -> ExecutionState:
        """Resume paused execution.
        
        Args:
            execution_state: Paused execution state
            max_retries: Maximum retries per step
            continue_on_error: Whether to continue on errors
            
        Returns:
            Updated execution state
        """
        if execution_state.status != ExecutionStatus.PAUSED:
            raise TaskExecutorError("Execution is not paused")
        
        logger.info("Resuming execution")
        return await self.execute(
            execution_state=execution_state,
            max_retries=max_retries,
            continue_on_error=continue_on_error
        )
    
    async def cancel_execution(self, execution_state: ExecutionState):
        """Cancel the current execution.
        
        Args:
            execution_state: Execution state to cancel
        """
        execution_state.cancel()
        logger.info("Execution cancelled")
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names.
        
        Returns:
            List of tool names
        """
        return list(self.tools.keys())