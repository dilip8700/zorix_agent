"""Plan preview generation for visualization and user approval."""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agent.planning.cost_estimator import PlanCost
from agent.planning.modes import PlanningMode

logger = logging.getLogger(__name__)


@dataclass
class PlanPreview:
    """Preview of a task execution plan."""
    title: str
    description: str
    mode: PlanningMode
    steps: List[Dict[str, Any]]
    cost: PlanCost
    
    # Preview details
    files_affected: List[str] = field(default_factory=list)
    commands_to_run: List[str] = field(default_factory=list)
    expected_outcomes: List[str] = field(default_factory=list)
    potential_risks: List[str] = field(default_factory=list)
    
    # Visual representation
    step_summaries: List[str] = field(default_factory=list)
    progress_indicators: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "description": self.description,
            "mode": self.mode.value,
            "steps": self.steps,
            "cost": self.cost.to_dict(),
            "files_affected": self.files_affected,
            "commands_to_run": self.commands_to_run,
            "expected_outcomes": self.expected_outcomes,
            "potential_risks": self.potential_risks,
            "step_summaries": self.step_summaries,
            "progress_indicators": self.progress_indicators,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanPreview":
        """Create from dictionary."""
        return cls(
            title=data["title"],
            description=data["description"],
            mode=PlanningMode(data["mode"]),
            steps=data["steps"],
            cost=PlanCost.from_dict(data["cost"]),
            files_affected=data.get("files_affected", []),
            commands_to_run=data.get("commands_to_run", []),
            expected_outcomes=data.get("expected_outcomes", []),
            potential_risks=data.get("potential_risks", []),
            step_summaries=data.get("step_summaries", []),
            progress_indicators=data.get("progress_indicators", []),
        )


class PreviewGenerator:
    """Generates human-readable previews of execution plans."""
    
    def __init__(self):
        """Initialize preview generator."""
        self.step_icons = {
            "read_file": "📖",
            "write_file": "✏️",
            "list_directory": "📁",
            "apply_patch": "🔧",
            "run_command": "⚡",
            "git_add": "📝",
            "git_commit": "💾",
            "git_branch": "🌿",
            "reasoning": "🤔",
            "validation": "✅",
        }
        
        self.mode_descriptions = {
            PlanningMode.EDIT: "Modify existing code and files",
            PlanningMode.EXPLAIN: "Analyze and explain code functionality",
            PlanningMode.REFACTOR: "Restructure code for better maintainability",
            PlanningMode.TEST: "Create and run tests for code validation",
            PlanningMode.CREATE: "Create new functionality and files",
            PlanningMode.DEBUG: "Identify and fix issues in code",
            PlanningMode.OPTIMIZE: "Improve code performance and efficiency",
            PlanningMode.DOCUMENT: "Add documentation and comments",
        }
        
        logger.info("Initialized PreviewGenerator")
    
    def generate_preview(
        self,
        instruction: str,
        steps: List[Dict[str, Any]],
        mode: PlanningMode,
        cost: PlanCost,
        context: Optional[Dict[str, Any]] = None
    ) -> PlanPreview:
        """Generate a comprehensive preview of the execution plan.
        
        Args:
            instruction: Original user instruction
            steps: List of execution steps
            mode: Planning mode
            cost: Cost estimation
            context: Additional context
            
        Returns:
            Plan preview
        """
        logger.info(f"Generating preview for {len(steps)} steps in {mode.value} mode")
        
        # Generate title and description
        title = self._generate_title(instruction, mode)
        description = self._generate_description(instruction, mode, steps)
        
        # Analyze steps for preview details
        files_affected = self._extract_affected_files(steps)
        commands_to_run = self._extract_commands(steps)
        expected_outcomes = self._extract_expected_outcomes(steps)
        potential_risks = cost.risk_factors + cost.safety_concerns
        
        # Generate step summaries and progress indicators
        step_summaries = self._generate_step_summaries(steps)
        progress_indicators = self._generate_progress_indicators(steps)
        
        preview = PlanPreview(
            title=title,
            description=description,
            mode=mode,
            steps=steps,
            cost=cost,
            files_affected=files_affected,
            commands_to_run=commands_to_run,
            expected_outcomes=expected_outcomes,
            potential_risks=potential_risks,
            step_summaries=step_summaries,
            progress_indicators=progress_indicators,
        )
        
        logger.info(f"Generated preview: {title}")
        return preview
    
    def _generate_title(self, instruction: str, mode: PlanningMode) -> str:
        """Generate a concise title for the plan.
        
        Args:
            instruction: User instruction
            mode: Planning mode
            
        Returns:
            Plan title
        """
        # Extract key action from instruction
        instruction_words = instruction.split()[:6]  # First 6 words
        key_phrase = " ".join(instruction_words)
        
        if len(instruction) > 50:
            key_phrase += "..."
        
        mode_prefix = {
            PlanningMode.EDIT: "Edit:",
            PlanningMode.EXPLAIN: "Explain:",
            PlanningMode.REFACTOR: "Refactor:",
            PlanningMode.TEST: "Test:",
            PlanningMode.CREATE: "Create:",
            PlanningMode.DEBUG: "Debug:",
            PlanningMode.OPTIMIZE: "Optimize:",
            PlanningMode.DOCUMENT: "Document:",
        }
        
        prefix = mode_prefix.get(mode, "Task:")
        return f"{prefix} {key_phrase}"
    
    def _generate_description(
        self,
        instruction: str,
        mode: PlanningMode,
        steps: List[Dict[str, Any]]
    ) -> str:
        """Generate a detailed description of what the plan will do.
        
        Args:
            instruction: User instruction
            mode: Planning mode
            steps: Execution steps
            
        Returns:
            Plan description
        """
        mode_desc = self.mode_descriptions.get(mode, "Execute the requested task")
        step_count = len(steps)
        
        # Count different types of operations
        file_ops = len([s for s in steps if s.get("tool_name") in ["read_file", "write_file", "apply_patch"]])
        command_ops = len([s for s in steps if s.get("tool_name") == "run_command"])
        git_ops = len([s for s in steps if s.get("tool_name") and s.get("tool_name").startswith("git_")])
        
        description_parts = [mode_desc]
        
        if step_count > 1:
            description_parts.append(f"This plan involves {step_count} steps")
        
        operation_details = []
        if file_ops > 0:
            operation_details.append(f"{file_ops} file operations")
        if command_ops > 0:
            operation_details.append(f"{command_ops} command executions")
        if git_ops > 0:
            operation_details.append(f"{git_ops} git operations")
        
        if operation_details:
            description_parts.append(f"including {', '.join(operation_details)}")
        
        return ". ".join(description_parts) + "."
    
    def _extract_affected_files(self, steps: List[Dict[str, Any]]) -> List[str]:
        """Extract list of files that will be affected.
        
        Args:
            steps: Execution steps
            
        Returns:
            List of file paths
        """
        files = set()
        
        for step in steps:
            tool_name = step.get("tool_name")
            tool_args = step.get("tool_args", {})
            
            if tool_name in ["read_file", "write_file", "apply_patch"]:
                file_path = tool_args.get("path") or tool_args.get("file_path")
                if file_path:
                    files.add(file_path)
        
        return sorted(list(files))
    
    def _extract_commands(self, steps: List[Dict[str, Any]]) -> List[str]:
        """Extract list of commands that will be executed.
        
        Args:
            steps: Execution steps
            
        Returns:
            List of commands
        """
        commands = []
        
        for step in steps:
            tool_name = step.get("tool_name")
            tool_args = step.get("tool_args", {})
            
            if tool_name == "run_command":
                command = tool_args.get("command")
                if command:
                    commands.append(command)
        
        return commands
    
    def _extract_expected_outcomes(self, steps: List[Dict[str, Any]]) -> List[str]:
        """Extract expected outcomes from steps.
        
        Args:
            steps: Execution steps
            
        Returns:
            List of expected outcomes
        """
        outcomes = []
        
        for step in steps:
            expected_outcome = step.get("expected_outcome")
            if expected_outcome:
                outcomes.append(expected_outcome)
        
        return outcomes
    
    def _generate_step_summaries(self, steps: List[Dict[str, Any]]) -> List[str]:
        """Generate human-readable summaries for each step.
        
        Args:
            steps: Execution steps
            
        Returns:
            List of step summaries
        """
        summaries = []
        
        for i, step in enumerate(steps, 1):
            tool_name = step.get("tool_name")
            description = step.get("description", f"Step {i}")
            
            # Get icon for step type
            icon = self.step_icons.get(tool_name, "🔹")
            
            # Create summary
            summary = f"{icon} {description}"
            
            # Add tool-specific details
            if tool_name == "write_file":
                file_path = step.get("tool_args", {}).get("path")
                if file_path:
                    summary += f" ({file_path})"
            
            elif tool_name == "run_command":
                command = step.get("tool_args", {}).get("command", "")
                if command:
                    # Truncate long commands
                    cmd_preview = command[:30] + "..." if len(command) > 30 else command
                    summary += f" ({cmd_preview})"
            
            summaries.append(summary)
        
        return summaries
    
    def _generate_progress_indicators(self, steps: List[Dict[str, Any]]) -> List[str]:
        """Generate progress indicators for visualization.
        
        Args:
            steps: Execution steps
            
        Returns:
            List of progress indicators
        """
        indicators = []
        total_steps = len(steps)
        
        for i in range(total_steps):
            # Create progress bar representation
            completed = "█" * i
            remaining = "░" * (total_steps - i)
            percentage = int((i / total_steps) * 100) if total_steps > 0 else 0
            
            indicator = f"[{completed}{remaining}] {percentage}%"
            indicators.append(indicator)
        
        # Add final completion indicator
        final_indicator = f"[{'█' * total_steps}] 100%"
        indicators.append(final_indicator)
        
        return indicators
    
    def format_preview_text(self, preview: PlanPreview) -> str:
        """Format preview as human-readable text.
        
        Args:
            preview: Plan preview
            
        Returns:
            Formatted preview text
        """
        lines = []
        
        # Title and description
        lines.append(f"# {preview.title}")
        lines.append("")
        lines.append(preview.description)
        lines.append("")
        
        # Cost information
        cost = preview.cost
        lines.append("## Cost Estimation")
        lines.append(f"- **Time**: ~{cost.estimated_time_minutes:.1f} minutes")
        lines.append(f"- **Complexity**: {cost.complexity_score:.1f}/1.0")
        lines.append(f"- **Risk Level**: {cost.risk_level.value}")
        lines.append(f"- **Approval Required**: {cost.approval_required.value}")
        lines.append("")
        
        # Steps overview
        lines.append("## Execution Steps")
        for summary in preview.step_summaries:
            lines.append(f"- {summary}")
        lines.append("")
        
        # Files affected
        if preview.files_affected:
            lines.append("## Files Affected")
            for file_path in preview.files_affected:
                lines.append(f"- {file_path}")
            lines.append("")
        
        # Commands to run
        if preview.commands_to_run:
            lines.append("## Commands to Execute")
            for command in preview.commands_to_run:
                lines.append(f"- `{command}`")
            lines.append("")
        
        # Potential risks
        if preview.potential_risks:
            lines.append("## Potential Risks")
            for risk in preview.potential_risks:
                lines.append(f"- ⚠️ {risk}")
            lines.append("")
        
        # Expected outcomes
        if preview.expected_outcomes:
            lines.append("## Expected Outcomes")
            for outcome in preview.expected_outcomes:
                lines.append(f"- ✅ {outcome}")
            lines.append("")
        
        return "\n".join(lines)
    
    def format_preview_json(self, preview: PlanPreview) -> Dict[str, Any]:
        """Format preview as structured JSON.
        
        Args:
            preview: Plan preview
            
        Returns:
            JSON-serializable preview data
        """
        return preview.to_dict()