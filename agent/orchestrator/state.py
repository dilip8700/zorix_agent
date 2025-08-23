"""Execution state management for agent orchestration."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Status of execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class StepType(Enum):
    """Types of execution steps."""
    PLAN = "plan"
    TOOL_CALL = "tool_call"
    REASONING = "reasoning"
    VALIDATION = "validation"
    ROLLBACK = "rollback"


@dataclass
class ExecutionStep:
    """A single step in the execution process."""
    id: str = field(default_factory=lambda: str(uuid4()))
    step_type: StepType = StepType.TOOL_CALL
    description: str = ""
    tool_name: Optional[str] = None
    tool_args: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def start(self):
        """Mark step as started."""
        self.status = ExecutionStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)
    
    def complete(self, result: Any = None):
        """Mark step as completed."""
        self.status = ExecutionStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        if result is not None:
            self.result = result
    
    def fail(self, error: str):
        """Mark step as failed."""
        self.status = ExecutionStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "step_type": self.step_type.value,
            "description": self.description,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "result": self.result,
            "error": self.error,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionStep":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            step_type=StepType(data["step_type"]),
            description=data["description"],
            tool_name=data.get("tool_name"),
            tool_args=data.get("tool_args", {}),
            result=data.get("result"),
            error=data.get("error"),
            status=ExecutionStatus(data["status"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            metadata=data.get("metadata", {}),
        )


@dataclass
class ExecutionState:
    """State of an execution session."""
    id: str = field(default_factory=lambda: str(uuid4()))
    instruction: str = ""
    plan: List[str] = field(default_factory=list)
    steps: List[ExecutionStep] = field(default_factory=list)
    status: ExecutionStatus = ExecutionStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_step_index: int = 0
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Rollback support
    rollback_points: List[Dict[str, Any]] = field(default_factory=list)
    can_rollback: bool = True
    
    def start(self):
        """Start execution."""
        self.status = ExecutionStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)
    
    def complete(self):
        """Complete execution."""
        self.status = ExecutionStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
    
    def fail(self, error: str):
        """Fail execution."""
        self.status = ExecutionStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.metadata["error"] = error
    
    def pause(self):
        """Pause execution."""
        self.status = ExecutionStatus.PAUSED
    
    def resume(self):
        """Resume execution."""
        self.status = ExecutionStatus.RUNNING
    
    def cancel(self):
        """Cancel execution."""
        self.status = ExecutionStatus.CANCELLED
        self.completed_at = datetime.now(timezone.utc)
    
    def add_step(self, step: ExecutionStep):
        """Add a step to the execution."""
        self.steps.append(step)
    
    def get_current_step(self) -> Optional[ExecutionStep]:
        """Get the current step being executed."""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None
    
    def advance_step(self):
        """Move to the next step."""
        self.current_step_index += 1
    
    def create_rollback_point(self, description: str = ""):
        """Create a rollback point."""
        if not self.can_rollback:
            return
        
        rollback_point = {
            "id": str(uuid4()),
            "description": description,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step_index": self.current_step_index,
            "context": self.context.copy(),
            "completed_steps": len([s for s in self.steps if s.status == ExecutionStatus.COMPLETED]),
        }
        
        self.rollback_points.append(rollback_point)
        logger.info(f"Created rollback point: {description}")
    
    def rollback_to_point(self, rollback_id: str) -> bool:
        """Rollback to a specific point."""
        if not self.can_rollback:
            logger.warning("Rollback is disabled for this execution")
            return False
        
        # Find the rollback point
        rollback_point = None
        for point in self.rollback_points:
            if point["id"] == rollback_id:
                rollback_point = point
                break
        
        if not rollback_point:
            logger.error(f"Rollback point not found: {rollback_id}")
            return False
        
        # Restore state
        self.current_step_index = rollback_point["step_index"]
        self.context = rollback_point["context"].copy()
        
        # Mark subsequent steps as pending
        for i in range(rollback_point["step_index"], len(self.steps)):
            step = self.steps[i]
            step.status = ExecutionStatus.PENDING
            step.result = None
            step.error = None
            step.started_at = None
            step.completed_at = None
        
        # Remove rollback points after this one
        self.rollback_points = [
            point for point in self.rollback_points
            if point["timestamp"] <= rollback_point["timestamp"]
        ]
        
        logger.info(f"Rolled back to: {rollback_point['description']}")
        return True
    
    def get_progress(self) -> Dict[str, Any]:
        """Get execution progress information."""
        completed_steps = len([s for s in self.steps if s.status == ExecutionStatus.COMPLETED])
        failed_steps = len([s for s in self.steps if s.status == ExecutionStatus.FAILED])
        total_steps = len(self.steps)
        
        progress_percentage = (completed_steps / total_steps * 100) if total_steps > 0 else 0
        
        return {
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "current_step_index": self.current_step_index,
            "progress_percentage": progress_percentage,
            "status": self.status.value,
            "can_rollback": self.can_rollback,
            "rollback_points": len(self.rollback_points),
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "instruction": self.instruction,
            "plan": self.plan,
            "steps": [step.to_dict() for step in self.steps],
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "current_step_index": self.current_step_index,
            "context": self.context,
            "metadata": self.metadata,
            "rollback_points": self.rollback_points,
            "can_rollback": self.can_rollback,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionState":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            instruction=data["instruction"],
            plan=data.get("plan", []),
            steps=[ExecutionStep.from_dict(step_data) for step_data in data.get("steps", [])],
            status=ExecutionStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            current_step_index=data.get("current_step_index", 0),
            context=data.get("context", {}),
            metadata=data.get("metadata", {}),
            rollback_points=data.get("rollback_points", []),
            can_rollback=data.get("can_rollback", True),
        )