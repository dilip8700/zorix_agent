"""Cost estimation and approval requirement detection for task planning."""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from agent.planning.modes import PlanningMode

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk levels for plan execution."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalLevel(Enum):
    """Approval levels required for execution."""
    NONE = "none"
    USER_CONFIRMATION = "user_confirmation"
    EXPLICIT_APPROVAL = "explicit_approval"
    ADMIN_APPROVAL = "admin_approval"


@dataclass
class PlanCost:
    """Cost estimation for a plan."""
    estimated_time_minutes: float
    complexity_score: float  # 0.0 to 1.0
    risk_level: RiskLevel
    approval_required: ApprovalLevel
    
    # Detailed cost breakdown
    file_modifications: int = 0
    new_files_created: int = 0
    lines_of_code_affected: int = 0
    external_dependencies: int = 0
    
    # Risk factors
    risk_factors: List[str] = field(default_factory=list)
    safety_concerns: List[str] = field(default_factory=list)
    
    # Cost justification
    reasoning: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "estimated_time_minutes": self.estimated_time_minutes,
            "complexity_score": self.complexity_score,
            "risk_level": self.risk_level.value,
            "approval_required": self.approval_required.value,
            "file_modifications": self.file_modifications,
            "new_files_created": self.new_files_created,
            "lines_of_code_affected": self.lines_of_code_affected,
            "external_dependencies": self.external_dependencies,
            "risk_factors": self.risk_factors,
            "safety_concerns": self.safety_concerns,
            "reasoning": self.reasoning,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanCost":
        """Create from dictionary."""
        return cls(
            estimated_time_minutes=data["estimated_time_minutes"],
            complexity_score=data["complexity_score"],
            risk_level=RiskLevel(data["risk_level"]),
            approval_required=ApprovalLevel(data["approval_required"]),
            file_modifications=data.get("file_modifications", 0),
            new_files_created=data.get("new_files_created", 0),
            lines_of_code_affected=data.get("lines_of_code_affected", 0),
            external_dependencies=data.get("external_dependencies", 0),
            risk_factors=data.get("risk_factors", []),
            safety_concerns=data.get("safety_concerns", []),
            reasoning=data.get("reasoning", ""),
        )


class CostEstimator:
    """Estimates cost and risk for task execution plans."""
    
    def __init__(self):
        """Initialize cost estimator."""
        # Base time estimates per operation type (in minutes)
        self.base_times = {
            "read_file": 0.1,
            "write_file": 0.5,
            "list_directory": 0.1,
            "apply_patch": 1.0,
            "run_command": 2.0,
            "git_operation": 0.5,
            "reasoning": 1.0,
            "validation": 0.5,
        }
        
        # Risk factors and their weights
        self.risk_factors = {
            "system_files": 0.8,
            "configuration_files": 0.6,
            "database_operations": 0.7,
            "network_operations": 0.5,
            "file_deletion": 0.9,
            "bulk_operations": 0.4,
            "external_commands": 0.6,
        }
        
        logger.info("Initialized CostEstimator")
    
    def estimate_plan_cost(
        self,
        steps: List[Dict[str, Any]],
        mode: PlanningMode,
        context: Optional[Dict[str, Any]] = None
    ) -> PlanCost:
        """Estimate the cost of executing a plan.
        
        Args:
            steps: List of plan steps
            mode: Planning mode
            context: Additional context
            
        Returns:
            Cost estimation
        """
        logger.info(f"Estimating cost for {len(steps)} steps in {mode.value} mode")
        
        # Initialize cost tracking
        total_time = 0.0
        complexity_factors = []
        risk_factors = []
        safety_concerns = []
        
        file_modifications = 0
        new_files_created = 0
        lines_affected = 0
        external_deps = 0
        
        # Analyze each step
        for step in steps:
            step_cost = self._estimate_step_cost(step, context)
            total_time += step_cost["time"]
            complexity_factors.append(step_cost["complexity"])
            risk_factors.extend(step_cost["risks"])
            safety_concerns.extend(step_cost["safety"])
            
            # Track specific metrics
            if step.get("tool_name") == "write_file":
                if step.get("tool_args", {}).get("create_new", False):
                    new_files_created += 1
                else:
                    file_modifications += 1
                
                # Estimate lines affected
                content = step.get("tool_args", {}).get("content", "")
                lines_affected += len(content.split("\n")) if content else 10
            
            elif step.get("tool_name") == "apply_patch":
                file_modifications += 1
                # Estimate lines from patch
                patch = step.get("tool_args", {}).get("patch", "")
                lines_affected += len([l for l in patch.split("\n") if l.startswith(("+", "-"))])
            
            elif step.get("tool_name") == "run_command":
                external_deps += 1
        
        # Calculate overall complexity
        avg_complexity = sum(complexity_factors) / len(complexity_factors) if complexity_factors else 0.0
        
        # Apply mode-specific adjustments
        mode_multiplier = self._get_mode_multiplier(mode)
        total_time *= mode_multiplier
        
        # Determine risk level
        risk_level = self._calculate_risk_level(risk_factors, mode, context)
        
        # Determine approval requirement
        approval_required = self._determine_approval_requirement(
            risk_level, total_time, file_modifications, safety_concerns
        )
        
        # Generate reasoning
        reasoning = self._generate_cost_reasoning(
            total_time, avg_complexity, risk_level, len(steps), mode
        )
        
        cost = PlanCost(
            estimated_time_minutes=total_time,
            complexity_score=min(1.0, avg_complexity),
            risk_level=risk_level,
            approval_required=approval_required,
            file_modifications=file_modifications,
            new_files_created=new_files_created,
            lines_of_code_affected=lines_affected,
            external_dependencies=external_deps,
            risk_factors=list(set(risk_factors)),
            safety_concerns=list(set(safety_concerns)),
            reasoning=reasoning,
        )
        
        logger.info(f"Estimated cost: {total_time:.1f}min, {risk_level.value} risk, {approval_required.value} approval")
        return cost
    
    def _estimate_step_cost(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Estimate cost for a single step.
        
        Args:
            step: Step definition
            context: Additional context
            
        Returns:
            Step cost breakdown
        """
        tool_name = step.get("tool_name")
        tool_args = step.get("tool_args", {})
        step_type = step.get("step_type", "tool_call")
        
        # Base time estimation
        if tool_name in self.base_times:
            base_time = self.base_times[tool_name]
        elif step_type == "reasoning":
            base_time = self.base_times["reasoning"]
        elif step_type == "validation":
            base_time = self.base_times["validation"]
        else:
            base_time = 1.0  # Default
        
        # Complexity factors
        complexity = 0.1  # Base complexity
        
        if tool_name == "write_file":
            content = tool_args.get("content", "")
            complexity += len(content) / 1000  # Complexity based on content length
            
        elif tool_name == "apply_patch":
            patch = tool_args.get("patch", "")
            complexity += len(patch.split("\n")) / 100  # Complexity based on patch size
            
        elif tool_name == "run_command":
            command = tool_args.get("command", "")
            complexity += 0.3  # Commands are inherently more complex
            if any(dangerous in command.lower() for dangerous in ["rm", "del", "format", "sudo"]):
                complexity += 0.5
        
        # Risk assessment
        risks = []
        safety = []
        
        if tool_name == "write_file":
            file_path = tool_args.get("path", "")
            if any(sys_path in file_path for sys_path in ["/etc/", "/sys/", "C:\\Windows\\"]):
                risks.append("system_files")
                safety.append("Modifying system files")
            
            if file_path.endswith((".config", ".conf", ".ini", ".env")):
                risks.append("configuration_files")
                safety.append("Modifying configuration files")
        
        elif tool_name == "run_command":
            command = tool_args.get("command", "")
            risks.append("external_commands")
            
            if any(dangerous in command.lower() for dangerous in ["rm", "del", "format"]):
                risks.append("file_deletion")
                safety.append("Command may delete files")
            
            if "sudo" in command.lower():
                safety.append("Command requires elevated privileges")
        
        return {
            "time": base_time,
            "complexity": complexity,
            "risks": risks,
            "safety": safety,
        }
    
    def _get_mode_multiplier(self, mode: PlanningMode) -> float:
        """Get time multiplier based on planning mode.
        
        Args:
            mode: Planning mode
            
        Returns:
            Time multiplier
        """
        multipliers = {
            PlanningMode.EDIT: 1.2,      # Editing requires careful consideration
            PlanningMode.EXPLAIN: 0.8,   # Explanation is mostly reading
            PlanningMode.REFACTOR: 1.5,  # Refactoring is complex
            PlanningMode.TEST: 1.3,      # Testing requires thoroughness
            PlanningMode.CREATE: 1.0,    # Baseline
            PlanningMode.DEBUG: 1.4,     # Debugging takes time
            PlanningMode.OPTIMIZE: 1.6,  # Optimization is complex
            PlanningMode.DOCUMENT: 0.9,  # Documentation is straightforward
        }
        return multipliers.get(mode, 1.0)
    
    def _calculate_risk_level(
        self,
        risk_factors: List[str],
        mode: PlanningMode,
        context: Optional[Dict[str, Any]] = None
    ) -> RiskLevel:
        """Calculate overall risk level.
        
        Args:
            risk_factors: List of identified risk factors
            mode: Planning mode
            context: Additional context
            
        Returns:
            Risk level
        """
        if not risk_factors:
            return RiskLevel.LOW
        
        # Calculate risk score
        risk_score = 0.0
        for factor in risk_factors:
            risk_score += self.risk_factors.get(factor, 0.1)
        
        # Mode-specific risk adjustments
        mode_risk = {
            PlanningMode.EDIT: 0.2,
            PlanningMode.EXPLAIN: 0.0,
            PlanningMode.REFACTOR: 0.3,
            PlanningMode.TEST: 0.1,
            PlanningMode.CREATE: 0.1,
            PlanningMode.DEBUG: 0.2,
            PlanningMode.OPTIMIZE: 0.3,
            PlanningMode.DOCUMENT: 0.0,
        }
        risk_score += mode_risk.get(mode, 0.1)
        
        # Context-based risk
        if context:
            if context.get("production_environment"):
                risk_score += 0.4
            if context.get("critical_files"):
                risk_score += 0.3
        
        # Determine risk level
        if risk_score >= 1.0:
            return RiskLevel.CRITICAL
        elif risk_score >= 0.7:
            return RiskLevel.HIGH
        elif risk_score >= 0.4:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _determine_approval_requirement(
        self,
        risk_level: RiskLevel,
        estimated_time: float,
        file_modifications: int,
        safety_concerns: List[str]
    ) -> ApprovalLevel:
        """Determine required approval level.
        
        Args:
            risk_level: Calculated risk level
            estimated_time: Estimated execution time
            file_modifications: Number of files to modify
            safety_concerns: List of safety concerns
            
        Returns:
            Required approval level
        """
        # Critical risk always requires admin approval
        if risk_level == RiskLevel.CRITICAL:
            return ApprovalLevel.ADMIN_APPROVAL
        
        # High risk or significant safety concerns require explicit approval
        if risk_level == RiskLevel.HIGH or len(safety_concerns) > 2:
            return ApprovalLevel.EXPLICIT_APPROVAL
        
        # Medium risk, long execution time, or many file changes require confirmation
        if (risk_level == RiskLevel.MEDIUM or 
            estimated_time > 30 or 
            file_modifications > 10):
            return ApprovalLevel.USER_CONFIRMATION
        
        # Low risk operations can proceed without approval
        return ApprovalLevel.NONE
    
    def _generate_cost_reasoning(
        self,
        time: float,
        complexity: float,
        risk_level: RiskLevel,
        step_count: int,
        mode: PlanningMode
    ) -> str:
        """Generate human-readable cost reasoning.
        
        Args:
            time: Estimated time
            complexity: Complexity score
            risk_level: Risk level
            step_count: Number of steps
            mode: Planning mode
            
        Returns:
            Cost reasoning text
        """
        reasoning_parts = []
        
        # Time estimation
        if time < 5:
            reasoning_parts.append("Quick task")
        elif time < 15:
            reasoning_parts.append("Moderate task")
        elif time < 60:
            reasoning_parts.append("Substantial task")
        else:
            reasoning_parts.append("Long-running task")
        
        reasoning_parts.append(f"with {step_count} steps")
        
        # Complexity
        if complexity > 0.7:
            reasoning_parts.append("high complexity")
        elif complexity > 0.4:
            reasoning_parts.append("moderate complexity")
        else:
            reasoning_parts.append("low complexity")
        
        # Risk
        reasoning_parts.append(f"and {risk_level.value} risk")
        
        # Mode-specific notes
        mode_notes = {
            PlanningMode.EDIT: "Requires careful file modification",
            PlanningMode.REFACTOR: "Involves code restructuring",
            PlanningMode.TEST: "Includes test creation and validation",
            PlanningMode.DEBUG: "May require iterative problem solving",
            PlanningMode.OPTIMIZE: "Involves performance analysis",
        }
        
        if mode in mode_notes:
            reasoning_parts.append(f"({mode_notes[mode]})")
        
        return ". ".join(reasoning_parts) + "."
    
    def should_require_approval(self, cost: PlanCost) -> bool:
        """Check if a plan requires user approval.
        
        Args:
            cost: Plan cost estimation
            
        Returns:
            True if approval is required
        """
        return cost.approval_required != ApprovalLevel.NONE
    
    def get_approval_message(self, cost: PlanCost) -> str:
        """Get approval message for user.
        
        Args:
            cost: Plan cost estimation
            
        Returns:
            Approval message
        """
        if cost.approval_required == ApprovalLevel.NONE:
            return ""
        
        message_parts = [
            f"This task is estimated to take {cost.estimated_time_minutes:.1f} minutes",
            f"with {cost.risk_level.value} risk level."
        ]
        
        if cost.file_modifications > 0:
            message_parts.append(f"It will modify {cost.file_modifications} files.")
        
        if cost.new_files_created > 0:
            message_parts.append(f"It will create {cost.new_files_created} new files.")
        
        if cost.safety_concerns:
            message_parts.append(f"Safety concerns: {', '.join(cost.safety_concerns)}")
        
        if cost.approval_required == ApprovalLevel.USER_CONFIRMATION:
            message_parts.append("Do you want to proceed?")
        elif cost.approval_required == ApprovalLevel.EXPLICIT_APPROVAL:
            message_parts.append("Please explicitly approve this task.")
        elif cost.approval_required == ApprovalLevel.ADMIN_APPROVAL:
            message_parts.append("This task requires administrator approval.")
        
        return " ".join(message_parts)