"""Enhanced task planner with mode-specific planning and cost estimation."""

import logging
from typing import Any, Dict, List, Optional

from agent.config import get_settings
from agent.llm.bedrock_client import BedrockClient
from agent.memory.provider import MemoryProvider
from agent.orchestrator.planner import TaskPlanner as BaseTaskPlanner
from agent.orchestrator.state import ExecutionState
from agent.planning.cost_estimator import CostEstimator
from agent.planning.modes import PlanningContext, PlanningMode, detect_planning_mode
from agent.planning.preview import PreviewGenerator

logger = logging.getLogger(__name__)


class TaskPlannerError(Exception):
    """Exception for task planning operations."""
    pass


class TaskPlanner:
    """Enhanced task planner with mode-specific planning and cost estimation."""
    
    def __init__(
        self,
        bedrock_client: Optional[BedrockClient] = None,
        memory_provider: Optional[MemoryProvider] = None,
    ):
        """Initialize enhanced task planner.
        
        Args:
            bedrock_client: Bedrock client for LLM operations
            memory_provider: Memory provider for context
        """
        self.bedrock = bedrock_client or BedrockClient()
        self.memory_provider = memory_provider
        self.settings = get_settings()
        
        # Initialize components
        self.base_planner = BaseTaskPlanner(
            bedrock_client=self.bedrock,
            memory_provider=self.memory_provider
        )
        self.cost_estimator = CostEstimator()
        self.preview_generator = PreviewGenerator()
        
        logger.info("Initialized enhanced TaskPlanner")
    
    async def create_plan(
        self,
        instruction: str,
        context: Optional[Dict[str, Any]] = None,
        planning_mode: Optional[PlanningMode] = None,
        available_tools: Optional[List[str]] = None,
        max_steps: int = 20,
        generate_preview: bool = True,
        estimate_cost: bool = True
    ) -> Dict[str, Any]:
        """Create an enhanced execution plan with cost estimation and preview.
        
        Args:
            instruction: The instruction to plan for
            context: Additional context information
            planning_mode: Specific planning mode (auto-detected if None)
            available_tools: List of available tool names
            max_steps: Maximum number of steps to generate
            generate_preview: Whether to generate plan preview
            estimate_cost: Whether to estimate execution cost
            
        Returns:
            Dictionary containing execution state, cost, and preview
        """
        logger.info(f"Creating enhanced plan for: {instruction[:100]}...")
        
        try:
            # Detect planning mode if not provided
            if planning_mode is None:
                planning_mode = detect_planning_mode(instruction, context)
            
            logger.info(f"Using planning mode: {planning_mode.value}")
            
            # Create planning context
            planning_context = self._create_planning_context(
                planning_mode, instruction, context
            )
            
            # Create base execution plan
            execution_state = await self.base_planner.create_plan(
                instruction=instruction,
                context=self._merge_context(context, planning_context),
                available_tools=available_tools,
                max_steps=max_steps
            )
            
            result = {
                "execution_state": execution_state,
                "planning_mode": planning_mode,
                "planning_context": planning_context,
            }
            
            # Estimate cost if requested
            if estimate_cost:
                cost = self.cost_estimator.estimate_plan_cost(
                    steps=[step.to_dict() for step in execution_state.steps],
                    mode=planning_mode,
                    context=context
                )
                result["cost"] = cost
                
                logger.info(f"Estimated cost: {cost.estimated_time_minutes:.1f}min, {cost.risk_level.value} risk")
            
            # Generate preview if requested
            if generate_preview:
                preview = self.preview_generator.generate_preview(
                    instruction=instruction,
                    steps=[step.to_dict() for step in execution_state.steps],
                    mode=planning_mode,
                    cost=result.get("cost"),
                    context=context
                )
                result["preview"] = preview
                
                logger.info(f"Generated preview: {preview.title}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to create enhanced plan: {e}")
            raise TaskPlannerError(f"Failed to create plan: {e}") from e
    
    async def create_mode_specific_plan(
        self,
        instruction: str,
        mode: PlanningMode,
        target_files: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a plan optimized for a specific mode.
        
        Args:
            instruction: The instruction to plan for
            mode: Specific planning mode
            target_files: Files to target for the operation
            context: Additional context
            **kwargs: Additional arguments for create_plan
            
        Returns:
            Enhanced plan result
        """
        logger.info(f"Creating {mode.value} plan for: {instruction[:100]}...")
        
        # Create mode-specific context
        mode_context = self._create_mode_specific_context(
            mode, instruction, target_files, context
        )
        
        # Merge with provided context
        merged_context = self._merge_context(context, mode_context)
        
        return await self.create_plan(
            instruction=instruction,
            context=merged_context,
            planning_mode=mode,
            **kwargs
        )
    
    def _create_planning_context(
        self,
        mode: PlanningMode,
        instruction: str,
        context: Optional[Dict[str, Any]] = None
    ) -> PlanningContext:
        """Create planning context for the given mode and instruction.
        
        Args:
            mode: Planning mode
            instruction: User instruction
            context: Additional context
            
        Returns:
            Planning context
        """
        planning_context = PlanningContext(mode=mode)
        
        # Extract target files from context or instruction
        if context and "target_files" in context:
            planning_context.target_files = context["target_files"]
        
        # Add mode-specific requirements
        mode_requirements = {
            PlanningMode.EDIT: [
                "Preserve existing functionality",
                "Maintain code style consistency",
                "Validate changes before applying"
            ],
            PlanningMode.EXPLAIN: [
                "Provide clear explanations",
                "Include relevant examples",
                "Explain complex concepts simply"
            ],
            PlanningMode.REFACTOR: [
                "Maintain behavioral equivalence",
                "Improve code readability",
                "Follow established patterns",
                "Update related tests"
            ],
            PlanningMode.TEST: [
                "Achieve good test coverage",
                "Include edge cases",
                "Use appropriate test patterns",
                "Ensure tests are maintainable"
            ],
            PlanningMode.CREATE: [
                "Follow project conventions",
                "Include proper documentation",
                "Consider error handling",
                "Plan for extensibility"
            ],
            PlanningMode.DEBUG: [
                "Identify root cause",
                "Provide minimal fix",
                "Add preventive measures",
                "Document the solution"
            ],
            PlanningMode.OPTIMIZE: [
                "Measure before optimizing",
                "Focus on bottlenecks",
                "Maintain correctness",
                "Document performance gains"
            ],
            PlanningMode.DOCUMENT: [
                "Use clear language",
                "Include examples",
                "Keep documentation current",
                "Follow documentation standards"
            ]
        }
        
        planning_context.requirements = mode_requirements.get(mode, [])
        
        # Add constraints based on context
        if context:
            planning_context.constraints.update(context.get("constraints", {}))
            planning_context.user_preferences.update(context.get("preferences", {}))
        
        return planning_context
    
    def _create_mode_specific_context(
        self,
        mode: PlanningMode,
        instruction: str,
        target_files: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create context specific to the planning mode.
        
        Args:
            mode: Planning mode
            instruction: User instruction
            target_files: Target files
            context: Additional context
            
        Returns:
            Mode-specific context
        """
        mode_context = {
            "planning_mode": mode.value,
            "target_files": target_files or [],
        }
        
        # Add mode-specific context
        if mode == PlanningMode.EDIT:
            mode_context.update({
                "preserve_functionality": True,
                "backup_original": True,
                "validate_syntax": True,
                "incremental_changes": True,
            })
        
        elif mode == PlanningMode.EXPLAIN:
            mode_context.update({
                "include_examples": True,
                "explain_complexity": True,
                "show_relationships": True,
                "use_diagrams": False,
            })
        
        elif mode == PlanningMode.REFACTOR:
            mode_context.update({
                "preserve_behavior": True,
                "improve_structure": True,
                "reduce_duplication": True,
                "enhance_readability": True,
                "update_tests": True,
            })
        
        elif mode == PlanningMode.TEST:
            mode_context.update({
                "test_coverage_target": 80,
                "include_unit_tests": True,
                "include_integration_tests": False,
                "mock_external_deps": True,
                "test_edge_cases": True,
            })
        
        elif mode == PlanningMode.CREATE:
            mode_context.update({
                "follow_conventions": True,
                "include_documentation": True,
                "add_error_handling": True,
                "consider_extensibility": True,
            })
        
        elif mode == PlanningMode.DEBUG:
            mode_context.update({
                "identify_root_cause": True,
                "minimal_changes": True,
                "add_logging": True,
                "prevent_regression": True,
            })
        
        elif mode == PlanningMode.OPTIMIZE:
            mode_context.update({
                "measure_performance": True,
                "profile_bottlenecks": True,
                "maintain_correctness": True,
                "document_improvements": True,
            })
        
        elif mode == PlanningMode.DOCUMENT:
            mode_context.update({
                "clear_language": True,
                "include_examples": True,
                "follow_standards": True,
                "keep_current": True,
            })
        
        return mode_context
    
    def _merge_context(
        self,
        base_context: Optional[Dict[str, Any]],
        additional_context: Any
    ) -> Dict[str, Any]:
        """Merge base context with additional context.
        
        Args:
            base_context: Base context dictionary
            additional_context: Additional context (dict or PlanningContext)
            
        Returns:
            Merged context dictionary
        """
        merged = base_context.copy() if base_context else {}
        
        if hasattr(additional_context, 'to_dict'):
            # PlanningContext object
            merged.update(additional_context.to_dict())
        elif isinstance(additional_context, dict):
            # Dictionary
            merged.update(additional_context)
        
        return merged
    
    async def refine_plan_for_mode(
        self,
        execution_state: ExecutionState,
        mode: PlanningMode,
        feedback: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Refine an existing plan with mode-specific considerations.
        
        Args:
            execution_state: Current execution state
            mode: Planning mode
            feedback: Feedback about the plan
            context: Additional context
            
        Returns:
            Refined plan result
        """
        logger.info(f"Refining plan for {mode.value} mode based on feedback")
        
        # Add mode-specific feedback context
        mode_feedback = f"Mode: {mode.value}. {feedback}"
        
        # Refine using base planner
        refined_state = await self.base_planner.refine_plan(
            execution_state=execution_state,
            feedback=mode_feedback
        )
        
        # Re-estimate cost and generate new preview
        cost = self.cost_estimator.estimate_plan_cost(
            steps=[step.to_dict() for step in refined_state.steps],
            mode=mode,
            context=context
        )
        
        preview = self.preview_generator.generate_preview(
            instruction=refined_state.instruction,
            steps=[step.to_dict() for step in refined_state.steps],
            mode=mode,
            cost=cost,
            context=context
        )
        
        return {
            "execution_state": refined_state,
            "planning_mode": mode,
            "cost": cost,
            "preview": preview,
        }
    
    def get_mode_recommendations(
        self,
        instruction: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Get recommendations for different planning modes.
        
        Args:
            instruction: User instruction
            context: Additional context
            
        Returns:
            List of mode recommendations with descriptions
        """
        recommendations = []
        
        # Detect primary mode
        primary_mode = detect_planning_mode(instruction, context)
        
        # Generate recommendations for each applicable mode
        for mode in PlanningMode:
            if self._is_mode_applicable(mode, instruction, context):
                recommendation = {
                    "mode": mode.value,
                    "is_primary": mode == primary_mode,
                    "description": self._get_mode_description(mode),
                    "suitability_score": self._calculate_mode_suitability(
                        mode, instruction, context
                    ),
                }
                recommendations.append(recommendation)
        
        # Sort by suitability score
        recommendations.sort(key=lambda x: x["suitability_score"], reverse=True)
        
        return recommendations
    
    def _is_mode_applicable(
        self,
        mode: PlanningMode,
        instruction: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if a planning mode is applicable to the instruction.
        
        Args:
            mode: Planning mode to check
            instruction: User instruction
            context: Additional context
            
        Returns:
            True if mode is applicable
        """
        instruction_lower = instruction.lower()
        
        # Mode applicability rules
        applicability_rules = {
            PlanningMode.EDIT: lambda: any(word in instruction_lower for word in 
                ["edit", "modify", "change", "update", "fix"]),
            PlanningMode.EXPLAIN: lambda: any(word in instruction_lower for word in 
                ["explain", "describe", "what", "how", "why"]),
            PlanningMode.REFACTOR: lambda: any(word in instruction_lower for word in 
                ["refactor", "restructure", "improve", "clean"]),
            PlanningMode.TEST: lambda: any(word in instruction_lower for word in 
                ["test", "verify", "validate", "check"]),
            PlanningMode.CREATE: lambda: any(word in instruction_lower for word in 
                ["create", "make", "build", "new", "add"]),
            PlanningMode.DEBUG: lambda: any(word in instruction_lower for word in 
                ["debug", "fix", "error", "bug", "issue"]),
            PlanningMode.OPTIMIZE: lambda: any(word in instruction_lower for word in 
                ["optimize", "performance", "speed", "efficiency"]),
            PlanningMode.DOCUMENT: lambda: any(word in instruction_lower for word in 
                ["document", "comment", "readme", "docs"]),
        }
        
        rule = applicability_rules.get(mode)
        return rule() if rule else True
    
    def _get_mode_description(self, mode: PlanningMode) -> str:
        """Get description for a planning mode.
        
        Args:
            mode: Planning mode
            
        Returns:
            Mode description
        """
        descriptions = {
            PlanningMode.EDIT: "Modify existing code and files with careful preservation of functionality",
            PlanningMode.EXPLAIN: "Analyze and explain code functionality with clear examples",
            PlanningMode.REFACTOR: "Restructure code for better maintainability while preserving behavior",
            PlanningMode.TEST: "Create comprehensive tests with good coverage and edge cases",
            PlanningMode.CREATE: "Build new functionality following best practices and conventions",
            PlanningMode.DEBUG: "Identify and fix issues with minimal, targeted changes",
            PlanningMode.OPTIMIZE: "Improve performance and efficiency while maintaining correctness",
            PlanningMode.DOCUMENT: "Add clear documentation and comments following standards",
        }
        return descriptions.get(mode, "Execute the requested task")
    
    def _calculate_mode_suitability(
        self,
        mode: PlanningMode,
        instruction: str,
        context: Optional[Dict[str, Any]] = None
    ) -> float:
        """Calculate suitability score for a mode.
        
        Args:
            mode: Planning mode
            instruction: User instruction
            context: Additional context
            
        Returns:
            Suitability score (0.0 to 1.0)
        """
        if not self._is_mode_applicable(mode, instruction, context):
            return 0.0
        
        instruction_lower = instruction.lower()
        
        # Mode-specific keyword weights
        keyword_weights = {
            PlanningMode.EDIT: {"edit": 0.9, "modify": 0.8, "change": 0.7, "update": 0.6, "fix": 0.5},
            PlanningMode.EXPLAIN: {"explain": 0.9, "describe": 0.8, "what": 0.6, "how": 0.7, "why": 0.8},
            PlanningMode.REFACTOR: {"refactor": 0.9, "restructure": 0.8, "improve": 0.6, "clean": 0.5},
            PlanningMode.TEST: {"test": 0.9, "verify": 0.7, "validate": 0.7, "check": 0.5},
            PlanningMode.CREATE: {"create": 0.9, "make": 0.7, "build": 0.8, "new": 0.6, "add": 0.5},
            PlanningMode.DEBUG: {"debug": 0.9, "fix": 0.7, "error": 0.6, "bug": 0.8, "issue": 0.6},
            PlanningMode.OPTIMIZE: {"optimize": 0.9, "performance": 0.8, "speed": 0.7, "efficiency": 0.7},
            PlanningMode.DOCUMENT: {"document": 0.9, "comment": 0.7, "readme": 0.8, "docs": 0.8},
        }
        
        weights = keyword_weights.get(mode, {})
        score = 0.0
        
        for keyword, weight in weights.items():
            if keyword in instruction_lower:
                score = max(score, weight)
        
        # Context-based adjustments
        if context:
            if context.get("files_to_modify") and mode == PlanningMode.EDIT:
                score += 0.2
            if context.get("create_tests") and mode == PlanningMode.TEST:
                score += 0.2
            if context.get("explain_code") and mode == PlanningMode.EXPLAIN:
                score += 0.2
        
        return min(1.0, score)