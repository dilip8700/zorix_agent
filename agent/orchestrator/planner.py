"""Task planning using LLM for instruction decomposition."""

import json
import logging
from typing import Any, Dict, List, Optional

from agent.config import get_settings
from agent.llm.bedrock_client import BedrockClient
from agent.llm.schemas import get_all_tool_schemas
from agent.memory.provider import MemoryProvider
from agent.orchestrator.state import ExecutionState, ExecutionStep, StepType

logger = logging.getLogger(__name__)


class TaskPlannerError(Exception):
    """Exception for task planning operations."""
    pass


class TaskPlanner:
    """Plans and decomposes instructions into executable steps."""
    
    def __init__(
        self,
        bedrock_client: Optional[BedrockClient] = None,
        memory_provider: Optional[MemoryProvider] = None,
    ):
        """Initialize task planner.
        
        Args:
            bedrock_client: Bedrock client for LLM operations
            memory_provider: Memory provider for context
        """
        self.bedrock = bedrock_client or BedrockClient()
        self.memory_provider = memory_provider
        self.settings = get_settings()
        
        logger.info("Initialized TaskPlanner")
    
    async def create_plan(
        self,
        instruction: str,
        context: Optional[Dict[str, Any]] = None,
        available_tools: Optional[List[str]] = None,
        max_steps: int = 20
    ) -> ExecutionState:
        """Create an execution plan from an instruction.
        
        Args:
            instruction: The instruction to plan for
            context: Additional context information
            available_tools: List of available tool names
            max_steps: Maximum number of steps to generate
            
        Returns:
            ExecutionState with planned steps
        """
        logger.info(f"Creating plan for instruction: {instruction[:100]}...")
        
        # Create execution state
        execution_state = ExecutionState(
            instruction=instruction,
            context=context or {},
        )
        
        try:
            # Get available tools and their schemas
            all_schemas = get_all_tool_schemas()
            tool_schemas = {schema["name"]: schema for schema in all_schemas}
            if available_tools:
                tool_schemas = {
                    name: schema for name, schema in tool_schemas.items()
                    if name in available_tools
                }
            
            # Get relevant context from memory
            memory_context = await self._get_memory_context(instruction)
            
            # Generate plan using LLM
            plan_steps = await self._generate_plan_with_llm(
                instruction=instruction,
                context=context or {},
                memory_context=memory_context,
                tool_schemas=tool_schemas,
                max_steps=max_steps
            )
            
            # Convert plan to execution steps
            for i, step_info in enumerate(plan_steps):
                step = ExecutionStep(
                    step_type=StepType.TOOL_CALL if step_info.get("tool_name") else StepType.REASONING,
                    description=step_info.get("description", f"Step {i+1}"),
                    tool_name=step_info.get("tool_name"),
                    tool_args=step_info.get("tool_args", {}),
                    metadata={
                        "step_number": i + 1,
                        "reasoning": step_info.get("reasoning", ""),
                        "expected_outcome": step_info.get("expected_outcome", ""),
                    }
                )
                execution_state.add_step(step)
            
            # Store the high-level plan
            execution_state.plan = [step.description for step in execution_state.steps]
            
            logger.info(f"Created plan with {len(execution_state.steps)} steps")
            return execution_state
            
        except Exception as e:
            logger.error(f"Failed to create plan: {e}")
            execution_state.fail(f"Planning failed: {str(e)}")
            raise TaskPlannerError(f"Failed to create plan: {e}") from e
    
    async def _get_memory_context(self, instruction: str) -> Dict[str, Any]:
        """Get relevant context from memory."""
        if not self.memory_provider:
            return {}
        
        try:
            # Search for relevant memories
            memory_results = await self.memory_provider.search_memories(
                query=instruction,
                max_results=5,
                include_conversations=True,
                include_project_memories=True
            )
            
            # Get current project context
            project_context = self.memory_provider.get_current_project()
            
            return {
                "relevant_memories": [
                    {
                        "content": result.entry.content[:200],
                        "summary": result.entry.summary,
                        "importance": result.entry.importance,
                        "type": result.entry.memory_type.value,
                    }
                    for result in memory_results
                ],
                "project_context": {
                    "name": project_context.name if project_context else None,
                    "description": project_context.description if project_context else None,
                    "file_patterns": project_context.file_patterns if project_context else [],
                    "dependencies": project_context.dependencies if project_context else [],
                } if project_context else None,
            }
            
        except Exception as e:
            logger.warning(f"Failed to get memory context: {e}")
            return {}
    
    async def _generate_plan_with_llm(
        self,
        instruction: str,
        context: Dict[str, Any],
        memory_context: Dict[str, Any],
        tool_schemas: Dict[str, Any],
        max_steps: int
    ) -> List[Dict[str, Any]]:
        """Generate plan using LLM."""
        
        # Create system prompt for planning
        system_prompt = self._create_planning_prompt(tool_schemas, memory_context)
        
        # Create user message with instruction and context
        user_message = self._create_user_planning_message(instruction, context)
        
        try:
            # Generate plan using Bedrock
            # Convert to Message objects
            from agent.models.base import Message
            messages = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=user_message)
            ]
            
            response_data = await self.bedrock.chat_with_tools(
                messages=messages,
                max_tokens=4000,
                temperature=0.1,  # Low temperature for consistent planning
            )
            
            # Extract text content from response
            if isinstance(response_data, dict) and "content" in response_data:
                response = response_data["content"]
            else:
                response = str(response_data)
            
            # Parse the response to extract plan steps
            plan_steps = self._parse_plan_response(response)
            
            # Validate and limit steps
            if len(plan_steps) > max_steps:
                logger.warning(f"Plan has {len(plan_steps)} steps, limiting to {max_steps}")
                plan_steps = plan_steps[:max_steps]
            
            return plan_steps
            
        except Exception as e:
            logger.error(f"LLM plan generation failed: {e}")
            # Fallback to simple plan
            return self._create_fallback_plan(instruction)
    
    def _create_planning_prompt(
        self,
        tool_schemas: Dict[str, Any],
        memory_context: Dict[str, Any]
    ) -> str:
        """Create system prompt for planning."""
        
        tool_descriptions = []
        for tool_name, schema in tool_schemas.items():
            description = schema.get("description", "")
            parameters = schema.get("parameters", {}).get("properties", {})
            param_list = ", ".join(parameters.keys())
            tool_descriptions.append(f"- {tool_name}: {description} (params: {param_list})")
        
        tools_text = "\n".join(tool_descriptions) if tool_descriptions else "No tools available"
        
        memory_text = ""
        if memory_context.get("relevant_memories"):
            memory_text = "\n\nRelevant context from memory:\n"
            for memory in memory_context["relevant_memories"]:
                memory_text += f"- {memory['summary']}: {memory['content'][:100]}...\n"
        
        project_text = ""
        if memory_context.get("project_context"):
            project = memory_context["project_context"]
            project_text = f"\n\nCurrent project: {project.get('name', 'Unknown')}\n"
            project_text += f"Description: {project.get('description', 'No description')}\n"
            if project.get("file_patterns"):
                project_text += f"File types: {', '.join(project['file_patterns'])}\n"
        
        return f"""You are an AI agent planner. Your job is to break down user instructions into a sequence of executable steps using available tools.

Available tools:
{tools_text}
{memory_text}
{project_text}

Guidelines:
1. Break down complex instructions into simple, atomic steps
2. Each step should have a clear purpose and expected outcome
3. Use appropriate tools for each step
4. Consider dependencies between steps
5. Include validation steps when appropriate
6. Keep steps focused and actionable
7. Provide reasoning for each step

Response format (JSON):
{{
  "plan": [
    {{
      "description": "Clear description of what this step does",
      "tool_name": "tool_to_use" or null for reasoning steps,
      "tool_args": {{"param1": "value1"}},
      "reasoning": "Why this step is needed",
      "expected_outcome": "What should happen after this step"
    }}
  ]
}}"""
    
    def _create_user_planning_message(
        self,
        instruction: str,
        context: Dict[str, Any]
    ) -> str:
        """Create user message for planning."""
        
        message = f"Please create a step-by-step plan for the following instruction:\n\n{instruction}"
        
        if context:
            message += f"\n\nAdditional context:\n{json.dumps(context, indent=2)}"
        
        message += "\n\nPlease provide a detailed plan in the specified JSON format."
        
        return message
    
    def _parse_plan_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response to extract plan steps."""
        try:
            # Try to extract JSON from the response
            response = response.strip()
            
            # Find JSON block
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON found in response")
            
            json_str = response[start_idx:end_idx]
            parsed = json.loads(json_str)
            
            if "plan" not in parsed:
                raise ValueError("No 'plan' key in response")
            
            plan_steps = parsed["plan"]
            
            # Validate each step
            validated_steps = []
            for step in plan_steps:
                if not isinstance(step, dict):
                    continue
                
                if "description" not in step:
                    continue
                
                validated_steps.append({
                    "description": step.get("description", ""),
                    "tool_name": step.get("tool_name"),
                    "tool_args": step.get("tool_args", {}),
                    "reasoning": step.get("reasoning", ""),
                    "expected_outcome": step.get("expected_outcome", ""),
                })
            
            return validated_steps
            
        except Exception as e:
            logger.error(f"Failed to parse plan response: {e}")
            logger.debug(f"Response was: {response}")
            raise TaskPlannerError(f"Failed to parse plan: {e}")
    
    def _create_fallback_plan(self, instruction: str) -> List[Dict[str, Any]]:
        """Create a simple fallback plan when LLM planning fails."""
        return [
            {
                "description": f"Execute instruction: {instruction}",
                "tool_name": None,
                "tool_args": {},
                "reasoning": "Fallback plan due to planning failure",
                "expected_outcome": "Complete the requested task",
            }
        ]
    
    async def refine_plan(
        self,
        execution_state: ExecutionState,
        feedback: str,
        failed_step_index: Optional[int] = None
    ) -> ExecutionState:
        """Refine an existing plan based on feedback or failures.
        
        Args:
            execution_state: Current execution state
            feedback: Feedback about the plan or execution
            failed_step_index: Index of step that failed (if any)
            
        Returns:
            Updated execution state with refined plan
        """
        logger.info(f"Refining plan based on feedback: {feedback[:100]}...")
        
        try:
            # Create context for refinement
            refinement_context = {
                "original_instruction": execution_state.instruction,
                "current_plan": [step.description for step in execution_state.steps],
                "feedback": feedback,
                "failed_step": failed_step_index,
                "completed_steps": [
                    step.description for step in execution_state.steps
                    if step.status.value == "completed"
                ],
            }
            
            # Generate refined plan
            refined_steps = await self._generate_refined_plan(refinement_context)
            
            # Update execution state
            # Keep completed steps, replace pending/failed ones
            new_steps = []
            
            for i, step in enumerate(execution_state.steps):
                if step.status.value == "completed":
                    new_steps.append(step)
                else:
                    break
            
            # Add refined steps
            for step_info in refined_steps:
                step = ExecutionStep(
                    step_type=StepType.TOOL_CALL if step_info.get("tool_name") else StepType.REASONING,
                    description=step_info.get("description", "Refined step"),
                    tool_name=step_info.get("tool_name"),
                    tool_args=step_info.get("tool_args", {}),
                    metadata={
                        "reasoning": step_info.get("reasoning", ""),
                        "expected_outcome": step_info.get("expected_outcome", ""),
                        "refined": True,
                    }
                )
                new_steps.append(step)
            
            execution_state.steps = new_steps
            execution_state.plan = [step.description for step in execution_state.steps]
            execution_state.current_step_index = len([s for s in new_steps if s.status.value == "completed"])
            
            logger.info(f"Refined plan now has {len(execution_state.steps)} steps")
            return execution_state
            
        except Exception as e:
            logger.error(f"Failed to refine plan: {e}")
            raise TaskPlannerError(f"Failed to refine plan: {e}") from e
    
    async def _generate_refined_plan(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate refined plan based on context."""
        
        system_prompt = """You are an AI agent planner tasked with refining an execution plan based on feedback or failures.

Your job is to:
1. Analyze what went wrong or what feedback was provided
2. Adjust the remaining steps to address the issues
3. Ensure the refined plan will successfully complete the original instruction

Response format (JSON):
{
  "plan": [
    {
      "description": "Clear description of what this step does",
      "tool_name": "tool_to_use" or null,
      "tool_args": {"param1": "value1"},
      "reasoning": "Why this step is needed and how it addresses the feedback",
      "expected_outcome": "What should happen after this step"
    }
  ]
}"""
        
        user_message = f"""Please refine the execution plan based on the following information:

Original instruction: {context['original_instruction']}

Current plan:
{json.dumps(context['current_plan'], indent=2)}

Feedback/Issue: {context['feedback']}

Completed steps: {context.get('completed_steps', [])}

Please provide a refined plan that addresses the feedback and continues from where the execution left off."""
        
        try:
            # Convert to Message objects
            from agent.models.base import Message
            messages = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=user_message)
            ]
            
            response_data = await self.bedrock.chat_with_tools(
                messages=messages,
                max_tokens=3000,
                temperature=0.1,
            )
            
            # Extract text content from response
            if isinstance(response_data, dict) and "content" in response_data:
                response = response_data["content"]
            else:
                response = str(response_data)
            
            return self._parse_plan_response(response)
            
        except Exception as e:
            logger.error(f"Failed to generate refined plan: {e}")
            # Return a simple continuation plan
            return [
                {
                    "description": f"Continue with original instruction addressing: {context['feedback']}",
                    "tool_name": None,
                    "tool_args": {},
                    "reasoning": "Fallback refinement due to planning failure",
                    "expected_outcome": "Address the feedback and complete the task",
                }
            ]