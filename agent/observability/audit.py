"""Audit logging for Zorix Agent operations."""

import json
import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel

from agent.observability.logging import get_logger

logger = get_logger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events."""
    FILE_CREATE = "file_create"
    FILE_MODIFY = "file_modify"
    FILE_DELETE = "file_delete"
    FILE_READ = "file_read"
    COMMAND_EXECUTE = "command_execute"
    GIT_OPERATION = "git_operation"
    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"
    TASK_FAIL = "task_fail"
    CHAT_MESSAGE = "chat_message"
    API_REQUEST = "api_request"
    SECURITY_EVENT = "security_event"
    CONFIGURATION_CHANGE = "configuration_change"
    USER_ACTION = "user_action"


class AuditEvent(BaseModel):
    """An audit event record."""
    event_id: str
    event_type: AuditEventType
    timestamp: datetime
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    resource: Optional[str] = None
    action: str
    details: Dict[str, Any] = {}
    success: bool = True
    error_message: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AuditLogger:
    """Handles audit logging for security and compliance."""
    
    def __init__(
        self,
        audit_file: Optional[str] = None,
        max_file_size: int = 100 * 1024 * 1024,  # 100MB
        backup_count: int = 5,
        enable_console: bool = False
    ):
        """Initialize audit logger.
        
        Args:
            audit_file: Path to audit log file
            max_file_size: Maximum file size before rotation
            backup_count: Number of backup files to keep
            enable_console: Whether to also log to console
        """
        self.audit_file = audit_file
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.enable_console = enable_console
        
        if audit_file:
            self.audit_path = Path(audit_file)
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            self.audit_path = None
        
        logger.info(
            "Audit logger initialized",
            audit_file=audit_file,
            max_file_size=max_file_size,
            backup_count=backup_count
        )
    
    def log_event(
        self,
        event_type: AuditEventType,
        action: str,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """Log an audit event.
        
        Args:
            event_type: Type of event
            action: Action performed
            resource: Resource affected
            details: Additional event details
            success: Whether the action was successful
            error_message: Error message if action failed
            user_id: User ID if available
            session_id: Session ID if available
            ip_address: IP address if available
            user_agent: User agent if available
            
        Returns:
            Event ID
        """
        import uuid
        
        event_id = str(uuid.uuid4())
        
        event = AuditEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            session_id=session_id,
            resource=resource,
            action=action,
            details=details or {},
            success=success,
            error_message=error_message,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Write to audit file
        if self.audit_path:
            self._write_to_file(event)
        
        # Log to console if enabled
        if self.enable_console:
            logger.info(
                "Audit event",
                event_id=event_id,
                event_type=event_type.value,
                action=action,
                resource=resource,
                success=success,
                user_id=user_id,
                session_id=session_id
            )
        
        return event_id
    
    def log_file_operation(
        self,
        operation: str,
        file_path: str,
        success: bool = True,
        error_message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """Log a file operation.
        
        Args:
            operation: Operation type (create, modify, delete, read)
            file_path: Path to the file
            success: Whether operation was successful
            error_message: Error message if failed
            details: Additional details
            user_id: User ID if available
            session_id: Session ID if available
            
        Returns:
            Event ID
        """
        event_type_map = {
            "create": AuditEventType.FILE_CREATE,
            "modify": AuditEventType.FILE_MODIFY,
            "delete": AuditEventType.FILE_DELETE,
            "read": AuditEventType.FILE_READ
        }
        
        event_type = event_type_map.get(operation, AuditEventType.FILE_MODIFY)
        
        file_details = {
            "file_path": file_path,
            "operation": operation,
            **(details or {})
        }
        
        # Add file metadata if file exists
        try:
            if Path(file_path).exists():
                stat = Path(file_path).stat()
                file_details.update({
                    "file_size": stat.st_size,
                    "file_mode": oct(stat.st_mode),
                    "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        except Exception as e:
            file_details["metadata_error"] = str(e)
        
        return self.log_event(
            event_type=event_type,
            action=f"File {operation}",
            resource=file_path,
            details=file_details,
            success=success,
            error_message=error_message,
            user_id=user_id,
            session_id=session_id
        )
    
    def log_command_execution(
        self,
        command: str,
        working_dir: Optional[str] = None,
        exit_code: Optional[int] = None,
        output: Optional[str] = None,
        error_output: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """Log command execution.
        
        Args:
            command: Command that was executed
            working_dir: Working directory
            exit_code: Command exit code
            output: Command output
            error_output: Command error output
            user_id: User ID if available
            session_id: Session ID if available
            
        Returns:
            Event ID
        """
        details = {
            "command": command,
            "working_dir": working_dir,
            "exit_code": exit_code
        }
        
        # Truncate output to prevent huge log entries
        if output:
            details["output"] = output[:1000] + "..." if len(output) > 1000 else output
        
        if error_output:
            details["error_output"] = error_output[:1000] + "..." if len(error_output) > 1000 else error_output
        
        return self.log_event(
            event_type=AuditEventType.COMMAND_EXECUTE,
            action="Execute command",
            resource=command,
            details=details,
            success=exit_code == 0 if exit_code is not None else True,
            error_message=error_output if exit_code != 0 else None,
            user_id=user_id,
            session_id=session_id
        )
    
    def log_git_operation(
        self,
        operation: str,
        repository: str,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """Log Git operation.
        
        Args:
            operation: Git operation (commit, push, pull, etc.)
            repository: Repository path
            details: Additional details
            success: Whether operation was successful
            error_message: Error message if failed
            user_id: User ID if available
            session_id: Session ID if available
            
        Returns:
            Event ID
        """
        git_details = {
            "operation": operation,
            "repository": repository,
            **(details or {})
        }
        
        return self.log_event(
            event_type=AuditEventType.GIT_OPERATION,
            action=f"Git {operation}",
            resource=repository,
            details=git_details,
            success=success,
            error_message=error_message,
            user_id=user_id,
            session_id=session_id
        )
    
    def log_task_event(
        self,
        task_id: str,
        event_type: AuditEventType,
        task_description: str,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """Log task-related event.
        
        Args:
            task_id: Task identifier
            event_type: Type of task event
            task_description: Description of the task
            details: Additional details
            success: Whether task was successful
            error_message: Error message if failed
            user_id: User ID if available
            session_id: Session ID if available
            
        Returns:
            Event ID
        """
        task_details = {
            "task_id": task_id,
            "task_description": task_description,
            **(details or {})
        }
        
        return self.log_event(
            event_type=event_type,
            action=f"Task {event_type.value.split('_')[1]}",
            resource=task_id,
            details=task_details,
            success=success,
            error_message=error_message,
            user_id=user_id,
            session_id=session_id
        )
    
    def log_security_event(
        self,
        event_description: str,
        severity: str = "medium",
        details: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> str:
        """Log security-related event.
        
        Args:
            event_description: Description of the security event
            severity: Severity level (low, medium, high, critical)
            details: Additional details
            user_id: User ID if available
            session_id: Session ID if available
            ip_address: IP address if available
            
        Returns:
            Event ID
        """
        security_details = {
            "severity": severity,
            "description": event_description,
            **(details or {})
        }
        
        return self.log_event(
            event_type=AuditEventType.SECURITY_EVENT,
            action="Security event",
            details=security_details,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address
        )
    
    def search_events(
        self,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        resource: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """Search audit events.
        
        Args:
            event_type: Filter by event type
            user_id: Filter by user ID
            session_id: Filter by session ID
            resource: Filter by resource
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum number of events to return
            
        Returns:
            List of matching audit events
        """
        if not self.audit_path or not self.audit_path.exists():
            return []
        
        events = []
        
        try:
            with open(self.audit_path, 'r') as f:
                for line in f:
                    if len(events) >= limit:
                        break
                    
                    try:
                        event_data = json.loads(line.strip())
                        event = AuditEvent(**event_data)
                        
                        # Apply filters
                        if event_type and event.event_type != event_type:
                            continue
                        
                        if user_id and event.user_id != user_id:
                            continue
                        
                        if session_id and event.session_id != session_id:
                            continue
                        
                        if resource and event.resource != resource:
                            continue
                        
                        if start_time and event.timestamp < start_time:
                            continue
                        
                        if end_time and event.timestamp > end_time:
                            continue
                        
                        events.append(event)
                        
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning("Failed to parse audit log line", error=str(e))
                        continue
        
        except Exception as e:
            logger.error("Failed to search audit events", error=str(e))
        
        return events
    
    def _write_to_file(self, event: AuditEvent):
        """Write audit event to file.
        
        Args:
            event: Audit event to write
        """
        if not self.audit_path:
            return
        
        try:
            # Check if file rotation is needed
            if self.audit_path.exists() and self.audit_path.stat().st_size > self.max_file_size:
                self._rotate_file()
            
            # Write event as JSON line
            with open(self.audit_path, 'a') as f:
                f.write(event.json() + '\n')
        
        except Exception as e:
            logger.error("Failed to write audit event", error=str(e), event_id=event.event_id)
    
    def _rotate_file(self):
        """Rotate audit log file."""
        if not self.audit_path or not self.audit_path.exists():
            return
        
        try:
            # Remove oldest backup
            oldest_backup = self.audit_path.with_suffix(f'.{self.backup_count}')
            if oldest_backup.exists():
                oldest_backup.unlink()
            
            # Rotate existing backups
            for i in range(self.backup_count - 1, 0, -1):
                current_backup = self.audit_path.with_suffix(f'.{i}')
                next_backup = self.audit_path.with_suffix(f'.{i + 1}')
                
                if current_backup.exists():
                    current_backup.rename(next_backup)
            
            # Move current file to .1
            self.audit_path.rename(self.audit_path.with_suffix('.1'))
            
            logger.info("Audit log file rotated")
        
        except Exception as e:
            logger.error("Failed to rotate audit log file", error=str(e))


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance.
    
    Returns:
        AuditLogger instance
    """
    global _audit_logger
    
    if _audit_logger is None:
        from agent.config import get_settings
        settings = get_settings()
        
        audit_file = getattr(settings, "audit_log_file", "logs/audit.log")
        _audit_logger = AuditLogger(audit_file=audit_file)
    
    return _audit_logger


# Convenience functions
def log_file_operation(operation: str, file_path: str, **kwargs) -> str:
    """Log a file operation."""
    return get_audit_logger().log_file_operation(operation, file_path, **kwargs)


def log_command_execution(command: str, **kwargs) -> str:
    """Log command execution."""
    return get_audit_logger().log_command_execution(command, **kwargs)


def log_git_operation(operation: str, repository: str, **kwargs) -> str:
    """Log Git operation."""
    return get_audit_logger().log_git_operation(operation, repository, **kwargs)


def log_security_event(event_description: str, **kwargs) -> str:
    """Log security event."""
    return get_audit_logger().log_security_event(event_description, **kwargs)