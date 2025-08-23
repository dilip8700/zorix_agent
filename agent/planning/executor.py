"""Enhanced plan executor with approval workflows and safety checks."""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from agent.config import get_settings
from agent.llm.bedrock_client import BedrockClient
from agent.memory.provider import MemoryProvider
from agent.orchestrator.executor import TaskExecutor
from agent.orchestrator.state import ExecutionState, ExecutionStatus
from agent.planning.cost_estimator import ApprovalLevel, PlanCost

logger = logging.getLogger(__name__)


class PlanExecutorError(Exception):
    """Exception for plan execution operations."""
    pass


class ApprovalRequest:
    """Represents a request for user approval."""
    
    def __init__(
        self,
        execution_id: str,
        cost: PlanCost,
        message: str,
        approval_level: ApprovalLevel
    ):
        self.execution_id = execution_id
        self.cost = cost
        self.message = message
        self.approval_level = approval_level
        self.approved = False
        self.response_message = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "execution_id": self.execution_id,
            "cost": self.cost.to_dict(),
            "message": self.message,
            "approval_level": self.approval_level.value,
            "approved": self.approved,
            "response_message": self.response_message,
        }


class PlanExecutor:
    """Enhanced executor with approval workflows and safety checks."""
    
    def __init__(
        self,
        bedrock_client: Optional[BedrockClient] = None,
        memory_provider: Optional[MemoryProvider] = None,
        workspace_root: Optional[str] = None,
    ):
        """Initialize plan executor.
        
        Args:
            bedrock_client: Bedrock client for LLM operations
            memory_provider: Memory provider for context
            workspace_root: Root directory for workspace operations
        """
        self.bedrock = bedrock_client or BedrockClient()
        self.memory_provider = memory_provider
        self.settings = get_settings()
        
        # Initialize base executor
        self.base_executor = TaskExecutor(
            bedrock_client=self.bedrock,
            memory_provider=self.memory_provider,
            workspace_root=workspace_root
        )
        
        # Approval management
        self.pending_approvals: Dict[str, ApprovalRequest] = {}
        self.approval_callbacks: List[Callable[[ApprovalRequest], None]] = []
        
        # Safety settings
        self.safety_checks_enabled = True
        self.dry_run_mode = False
        
        logger.info("Initialized PlanExecutor")
    
    def add_approval_callback(self, callback: Callable[[ApprovalRequest], None]):
        """Add callback for approval requests.
        
        Args:
            callback: Callback function that receives ApprovalRequest
        """
        self.approval_callbacks.append(callback)
    
    def enable_safety_checks(self, enabled: bool = True):
        """Enable or disable safety checks.
        
        Args:
            enabled: Whether to enable safety checks
        """
        self.safety_checks_enabled = enabled
        logger.info(f"Safety checks {'enabled' if enabled else 'disabled'}")
    
    def set_dry_run_mode(self, enabled: bool = True):
        """Enable or disable dry run mode.
        
        Args:
            enabled: Whether to enable dry run mode
        """
        self.dry_run_mode = enabled
        logger.info(f"Dry run mode {'enabled' if enabled else 'disabled'}")
    
    async def execute_with_approval(
        self,
        execution_state: ExecutionState,
        cost: PlanCost,
        approval_message: str = "",
        timeout_seconds: int = 300,
        **kwargs
    ) -> ExecutionState:
        """Execute plan with approval workflow if required.
        
        Args:
            execution_state: Execution state to execute
            cost: Cost estimation for the plan
            approval_message: Custom approval message
            timeout_seconds: Timeout for approval request
            **kwargs: Additional arguments for execution
            
        Returns:
            Updated execution state
        """
        logger.info(f"Executing plan with approval workflow: {execution_state.id}")
        
        try:
            # Check if approval is required
            if cost.approval_required != ApprovalLevel.NONE:
                logger.info(f"Approval required: {cost.approval_required.value}")
                
                # Request approval
                approved = await self._request_approval(
                    execution_state, cost, approval_message, timeout_seconds
                )
                
                if not approved:
                    execution_state.cancel()
                    execution_state.metadata["cancellation_reason"] = "User denied approval"
                    logger.info("Execution cancelled: approval denied")
                    return execution_state
            
            # Perform safety checks if enabled
            if self.safety_checks_enabled:
                safety_result = await self._perform_safety_checks(execution_state)
                if not safety_result["safe"]:
                    execution_state.fail(f"Safety check failed: {safety_result['reason']}")
                    logger.error(f"Safety check failed: {safety_result['reason']}")
                    return execution_state
            
            # Execute in dry run mode if enabled
            if self.dry_run_mode:
                return await self._execute_dry_run(execution_state)
            
            # Execute normally
            return await self.base_executor.execute(execution_state, **kwargs)
            
        except Exception as e:
            logger.error(f"Execution with approval failed: {e}")
            execution_state.fail(f"Execution failed: {str(e)}")
            raise PlanExecutorError(f"Execution failed: {e}") from e
    
    async def _request_approval(
        self,
        execution_state: ExecutionState,
        cost: PlanCost,
        custom_message: str,
        timeout_seconds: int
    ) -> bool:
        """Request approval from user.
        
        Args:
            execution_state: Execution state
            cost: Cost estimation
            custom_message: Custom approval message
            timeout_seconds: Timeout for approval
            
        Returns:
            True if approved
        """
        # Create approval request
        message = custom_message or self._generate_approval_message(cost)
        
        approval_request = ApprovalRequest(
            execution_id=execution_state.id,
            cost=cost,
            message=message,
            approval_level=cost.approval_required
        )
        
        # Store pending approval
        self.pending_approvals[execution_state.id] = approval_request
        
        # Notify callbacks
        for callback in self.approval_callbacks:
            try:
                callback(approval_request)
            except Exception as e:
                logger.error(f"Approval callback error: {e}")
        
        # Wait for approval with timeout
        try:
            await asyncio.wait_for(
                self._wait_for_approval(execution_state.id),
                timeout=timeout_seconds
            )
            
            # Check approval result
            approval_request = self.pending_approvals.get(execution_state.id)
            if approval_request:
                approved = approval_request.approved
                logger.info(f"Approval result: {'approved' if approved else 'denied'}")
                return approved
            
            return False
            
        except asyncio.TimeoutError:
            logger.warning(f"Approval timeout for execution {execution_state.id}")
            return False
        
        finally:
            # Clean up pending approval
            self.pending_approvals.pop(execution_state.id, None)
    
    async def _wait_for_approval(self, execution_id: str):
        """Wait for approval response.
        
        Args:
            execution_id: Execution ID to wait for
        """
        while execution_id in self.pending_approvals:
            approval_request = self.pending_approvals[execution_id]
            if approval_request.approved or approval_request.response_message:
                break
            await asyncio.sleep(0.1)
    
    def approve_execution(
        self,
        execution_id: str,
        approved: bool = True,
        response_message: str = ""
    ) -> bool:
        """Approve or deny a pending execution.
        
        Args:
            execution_id: Execution ID to approve/deny
            approved: Whether to approve the execution
            response_message: Optional response message
            
        Returns:
            True if approval was processed
        """
        if execution_id not in self.pending_approvals:
            logger.warning(f"No pending approval for execution {execution_id}")
            return False
        
        approval_request = self.pending_approvals[execution_id]
        approval_request.approved = approved
        approval_request.response_message = response_message
        
        logger.info(f"Execution {execution_id} {'approved' if approved else 'denied'}")
        return True
    
    async def _perform_safety_checks(self, execution_state: ExecutionState) -> Dict[str, Any]:
        """Perform safety checks on the execution plan.
        
        Args:
            execution_state: Execution state to check
            
        Returns:
            Safety check result
        """
        logger.info("Performing safety checks")
        
        safety_issues = []
        
        # Check for dangerous operations
        for step in execution_state.steps:
            tool_name = step.tool_name
            tool_args = step.tool_args or {}
            
            # File system safety checks
            if tool_name == "write_file":
                file_path = tool_args.get("path", "")
                
                # Check for system file modifications
                if self._is_system_file(file_path):
                    safety_issues.append(f"Attempting to modify system file: {file_path}")
                
                # Check for suspicious file extensions
                if self._is_suspicious_file(file_path):
                    safety_issues.append(f"Attempting to create suspicious file: {file_path}")
            
            # Command execution safety checks
            elif tool_name == "run_command":
                command = tool_args.get("command", "")
                
                # Check for dangerous commands
                dangerous_commands = ["rm -rf", "del /s", "format", "fdisk", "dd if="]
                if any(dangerous in command.lower() for dangerous in dangerous_commands):
                    safety_issues.append(f"Dangerous command detected: {command}")
                
                # Check for privilege escalation
                if any(priv in command.lower() for priv in ["sudo", "su ", "runas"]):
                    safety_issues.append(f"Privilege escalation detected: {command}")
        
        # Check execution context
        if execution_state.context.get("production_environment"):
            safety_issues.append("Execution in production environment")
        
        # Return safety result
        if safety_issues:
            return {
                "safe": False,
                "reason": "; ".join(safety_issues),
                "issues": safety_issues
            }
        
        return {"safe": True, "reason": "All safety checks passed", "issues": []}
    
    def _is_system_file(self, file_path: str) -> bool:
        """Check if a file path is a system file.
        
        Args:
            file_path: File path to check
            
        Returns:
            True if it's a system file
        """
        system_paths = [
            "/etc/", "/sys/", "/proc/", "/dev/",
            "C:\\Windows\\", "C:\\System32\\", "C:\\Program Files\\",
            "/usr/bin/", "/usr/sbin/", "/bin/", "/sbin/"
        ]
        
        return any(system_path in file_path for system_path in system_paths)
    
    def _is_suspicious_file(self, file_path: str) -> bool:
        """Check if a file path is suspicious.
        
        Args:
            file_path: File path to check
            
        Returns:
            True if it's suspicious
        """
        suspicious_extensions = [
            ".exe", ".bat", ".cmd", ".scr", ".com", ".pif",
            ".sh", ".bash", ".zsh", ".fish"
        ]
        
        return any(file_path.lower().endswith(ext) for ext in suspicious_extensions)
    
    async def _execute_dry_run(self, execution_state: ExecutionState) -> ExecutionState:
        """Execute plan in dry run mode (simulation).
        
        Args:
            execution_state: Execution state to simulate
            
        Returns:
            Simulated execution state
        """
        logger.info("Executing in dry run mode")
        
        execution_state.start()
        
        # Simulate each step
        for i, step in enumerate(execution_state.steps):
            execution_state.current_step_index = i
            
            step.start()
            
            # Simulate step execution
            await asyncio.sleep(0.1)  # Small delay for realism
            
            # Generate simulated result
            simulated_result = self._generate_simulated_result(step)
            step.complete(simulated_result)
            
            # Create rollback point
            execution_state.create_rollback_point(f"Dry run step {i+1}")
        
        execution_state.complete()
        execution_state.metadata["dry_run"] = True
        
        logger.info("Dry run execution completed")
        return execution_state
    
    def _generate_simulated_result(self, step) -> str:
        """Generate simulated result for a step.
        
        Args:
            step: Execution step
            
        Returns:
            Simulated result
        """
        tool_name = step.tool_name
        
        if tool_name == "read_file":
            return "Simulated file content"
        elif tool_name == "write_file":
            return "File would be written successfully"
        elif tool_name == "list_directory":
            return "Directory listing would be returned"
        elif tool_name == "run_command":
            return "Command would execute successfully"
        elif tool_name and tool_name.startswith("git_"):
            return "Git operation would complete successfully"
        else:
            return f"Step '{step.description}' would complete successfully"
    
    def _generate_approval_message(self, cost: PlanCost) -> str:
        """Generate approval message from cost estimation.
        
        Args:
            cost: Cost estimation
            
        Returns:
            Approval message
        """
        message_parts = [
            f"This task will take approximately {cost.estimated_time_minutes:.1f} minutes",
            f"with {cost.risk_level.value} risk level."
        ]
        
        if cost.file_modifications > 0:
            message_parts.append(f"It will modify {cost.file_modifications} files.")
        
        if cost.new_files_created > 0:
            message_parts.append(f"It will create {cost.new_files_created} new files.")
        
        if cost.external_dependencies > 0:
            message_parts.append(f"It will execute {cost.external_dependencies} external commands.")
        
        if cost.safety_concerns:
            message_parts.append(f"Safety concerns: {', '.join(cost.safety_concerns)}")
        
        if cost.approval_required == ApprovalLevel.USER_CONFIRMATION:
            message_parts.append("Do you want to proceed?")
        elif cost.approval_required == ApprovalLevel.EXPLICIT_APPROVAL:
            message_parts.append("Please explicitly approve this task.")
        elif cost.approval_required == ApprovalLevel.ADMIN_APPROVAL:
            message_parts.append("This task requires administrator approval.")
        
        return " ".join(message_parts)
    
    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """Get list of pending approval requests.
        
        Returns:
            List of pending approvals
        """
        return [approval.to_dict() for approval in self.pending_approvals.values()]
    
    def cancel_pending_approval(self, execution_id: str) -> bool:
        """Cancel a pending approval request.
        
        Args:
            execution_id: Execution ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        if execution_id in self.pending_approvals:
            del self.pending_approvals[execution_id]
            logger.info(f"Cancelled pending approval for execution {execution_id}")
            return True
        
        return False
    
    # Delegate other methods to base executor
    async def execute(self, execution_state: ExecutionState, **kwargs) -> ExecutionState:
        """Execute plan using base executor."""
        return await self.base_executor.execute(execution_state, **kwargs)
    
    async def pause_execution(self, execution_state: ExecutionState):
        """Pause execution using base executor."""
        return await self.base_executor.pause_execution(execution_state)
    
    async def resume_execution(self, execution_state: ExecutionState, **kwargs) -> ExecutionState:
        """Resume execution using base executor."""
        return await self.base_executor.resume_execution(execution_state, **kwargs)
    
    async def cancel_execution(self, execution_state: ExecutionState):
        """Cancel execution using base executor."""
        return await self.base_executor.cancel_execution(execution_state)
    
    def get_available_tools(self) -> List[str]:
        """Get available tools from base executor."""
        return self.base_executor.get_available_tools()
    
    def add_tool(self, name: str, tool_func: Callable):
        """Add tool to base executor."""
        return self.base_executor.add_tool(name, tool_func)
    
    def add_step_callback(self, event: str, callback: Callable):
        """Add step callback to base executor."""
        return self.base_executor.add_step_callback(event, callback)