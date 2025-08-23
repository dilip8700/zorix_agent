"""Planning modes and context for different types of tasks."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PlanningMode(Enum):
    """Different modes of planning for various task types."""
    EDIT = "edit"
    EXPLAIN = "explain"
    REFACTOR = "refactor"
    TEST = "test"
    CREATE = "create"
    DEBUG = "debug"
    OPTIMIZE = "optimize"
    DOCUMENT = "document"


@dataclass
class PlanningContext:
    """Context information for planning tasks."""
    mode: PlanningMode
    target_files: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    
    # Mode-specific context
    edit_context: Optional[Dict[str, Any]] = None
    explain_context: Optional[Dict[str, Any]] = None
    refactor_context: Optional[Dict[str, Any]] = None
    test_context: Optional[Dict[str, Any]] = None
    
    def get_mode_context(self) -> Dict[str, Any]:
        """Get context specific to the current mode."""
        context_map = {
            PlanningMode.EDIT: self.edit_context or {},
            PlanningMode.EXPLAIN: self.explain_context or {},
            PlanningMode.REFACTOR: self.refactor_context or {},
            PlanningMode.TEST: self.test_context or {},
        }
        return context_map.get(self.mode, {})
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "mode": self.mode.value,
            "target_files": self.target_files,
            "requirements": self.requirements,
            "constraints": self.constraints,
            "user_preferences": self.user_preferences,
            "edit_context": self.edit_context,
            "explain_context": self.explain_context,
            "refactor_context": self.refactor_context,
            "test_context": self.test_context,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanningContext":
        """Create from dictionary."""
        return cls(
            mode=PlanningMode(data["mode"]),
            target_files=data.get("target_files", []),
            requirements=data.get("requirements", []),
            constraints=data.get("constraints", {}),
            user_preferences=data.get("user_preferences", {}),
            edit_context=data.get("edit_context"),
            explain_context=data.get("explain_context"),
            refactor_context=data.get("refactor_context"),
            test_context=data.get("test_context"),
        )


def detect_planning_mode(instruction: str, context: Optional[Dict[str, Any]] = None) -> PlanningMode:
    """Detect the appropriate planning mode from instruction and context.
    
    Args:
        instruction: The user instruction
        context: Additional context information
        
    Returns:
        Detected planning mode
    """
    instruction_lower = instruction.lower()
    
    # Mode detection keywords
    mode_keywords = {
        PlanningMode.EDIT: ["edit", "modify", "change", "update", "fix", "correct"],
        PlanningMode.EXPLAIN: ["explain", "describe", "what does", "how does", "why", "analyze"],
        PlanningMode.REFACTOR: ["refactor", "restructure", "reorganize", "improve", "clean up"],
        PlanningMode.TEST: ["test", "unit test", "integration test", "verify", "validate"],
        PlanningMode.CREATE: ["create", "make", "build", "generate", "new", "add"],
        PlanningMode.DEBUG: ["debug", "troubleshoot", "find bug", "error", "issue"],
        PlanningMode.OPTIMIZE: ["optimize", "performance", "speed up", "improve efficiency"],
        PlanningMode.DOCUMENT: ["document", "comment", "docstring", "readme", "documentation"],
    }
    
    # Check for explicit mode keywords
    for mode, keywords in mode_keywords.items():
        if any(keyword in instruction_lower for keyword in keywords):
            return mode
    
    # Check context for hints
    if context:
        if context.get("files_to_modify"):
            return PlanningMode.EDIT
        if context.get("explain_code"):
            return PlanningMode.EXPLAIN
        if context.get("create_tests"):
            return PlanningMode.TEST
    
    # Default to CREATE for new functionality
    return PlanningMode.CREATE


def create_mode_specific_context(
    mode: PlanningMode,
    instruction: str,
    files: Optional[List[str]] = None,
    additional_context: Optional[Dict[str, Any]] = None
) -> PlanningContext:
    """Create mode-specific planning context.
    
    Args:
        mode: Planning mode
        instruction: User instruction
        files: Target files
        additional_context: Additional context
        
    Returns:
        Planning context with mode-specific information
    """
    context = PlanningContext(
        mode=mode,
        target_files=files or [],
    )
    
    # Add mode-specific context
    if mode == PlanningMode.EDIT:
        context.edit_context = {
            "preserve_functionality": True,
            "backup_files": True,
            "validate_syntax": True,
            "run_tests_after": True,
        }
    
    elif mode == PlanningMode.EXPLAIN:
        context.explain_context = {
            "include_examples": True,
            "explain_complexity": True,
            "show_relationships": True,
            "include_diagrams": False,
        }
    
    elif mode == PlanningMode.REFACTOR:
        context.refactor_context = {
            "preserve_behavior": True,
            "improve_readability": True,
            "reduce_complexity": True,
            "follow_patterns": True,
            "update_tests": True,
        }
    
    elif mode == PlanningMode.TEST:
        context.test_context = {
            "test_coverage": "high",
            "include_edge_cases": True,
            "mock_dependencies": True,
            "integration_tests": False,
        }
    
    # Merge additional context
    if additional_context:
        context.constraints.update(additional_context.get("constraints", {}))
        context.user_preferences.update(additional_context.get("preferences", {}))
        context.requirements.extend(additional_context.get("requirements", []))
    
    return context