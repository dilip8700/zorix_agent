"""Agent orchestrator implementing ReAct pattern."""

import logging
import json
from typing import Any, Dict, List, Optional, AsyncGenerator
from uuid import uuid4

from agent.llm.bedrock_client import BedrockClient
from agent.memory.provider import MemoryProvider
from agent.vector.index import VectorIndex
from agent.tools.filesystem import FilesystemTools
from agent.tools.command import CommandTools
from agent.tools.git import GitTools
from agent.llm.schemas import get_all_tool_schemas

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Main orchestrator implementing ReAct pattern."""
    
    def __init__(
        self,
        bedrock_client: BedrockClient,
        memory_provider: MemoryProvider,
        vector_index: VectorIndex,
        filesystem_tools: FilesystemTools,
        command_tools: CommandTools,
        git_tools: GitTools
    ):
        """Initialize orchestrator."""
        self.bedrock_client = bedrock_client
        self.memory_provider = memory_provider
        self.vector_index = vector_index
        self.filesystem_tools = filesystem_tools
        self.command_tools = command_tools
        self.git_tools = git_tools
        
        # Get tool schemas and convert to dictionary for easy lookup
        schemas_list = get_all_tool_schemas()
        self.tool_schemas = {schema["name"]: schema for schema in schemas_list}
        
        logger.info("Initialized AgentOrchestrator")
    
    async def create_plan(
        self,
        instruction: str,
        mode: str = "auto",
        budget: Optional[Dict[str, Any]] = None,
        auto_apply: bool = False
    ) -> Dict[str, Any]:
        """Create an execution plan from an instruction."""
        logger.info(f"Creating plan for instruction: {instruction[:100]}...")
        
        try:
            # Generate plan using LLM
            plan_steps = await self._generate_plan_with_llm(instruction, mode, budget)
            
            # Create plan result
            plan_id = str(uuid4())
            plan_result = {
                "plan_id": plan_id,
                "instruction": instruction,
                "mode": mode,
                "steps": plan_steps,
                "budget": budget or {},
                "auto_apply": auto_apply
            }
            
            # Store plan in memory
            # await self.memory_provider.store_plan(plan_id, plan_result)
            
            logger.info(f"Created plan with {len(plan_steps)} steps")
            return plan_result
            
        except Exception as e:
            logger.error(f"Failed to create plan: {e}")
            raise
    
    async def apply_plan(
        self,
        plan: Dict[str, Any],
        approve_all: bool = False
    ) -> Dict[str, Any]:
        """Apply a previously created plan."""
        logger.info(f"Applying plan: {plan.get('plan_id', 'unknown')}")
        
        try:
            plan_id = plan.get("plan_id")
            steps = plan.get("steps", [])
            
            if not steps:
                raise ValueError("Plan has no steps")
            
            results = []
            applied_files = []
            commands_run = []
            
            # Execute each step
            for i, step in enumerate(steps):
                logger.info(f"Executing step {i+1}/{len(steps)}: {step.get('description', 'Unknown')}")
                
                try:
                    step_result = await self._execute_step(step)
                    results.append({
                        "step_index": i,
                        "status": "success",
                        "result": step_result
                    })
                    
                    # Track applied files and commands
                    if step_result.get("files_affected"):
                        applied_files.extend(step_result["files_affected"])
                    if step_result.get("command"):
                        commands_run.append(step_result["command"])
                    
                except Exception as e:
                    logger.error(f"Step {i+1} failed: {e}")
                    results.append({
                        "step_index": i,
                        "status": "failed",
                        "error": str(e)
                    })
                    
                    if not approve_all:
                        # Stop execution on first failure unless auto-approve
                        break
            
            # Create result
            result = {
                "plan_id": plan_id,
                "applied": applied_files,
                "commands": commands_run,
                "step_results": results,
                "success": all(r["status"] == "success" for r in results)
            }
            
            # Store execution result in memory
            # await self.memory_provider.store_execution_result(plan_id, result)
            
            logger.info(f"Plan execution completed: {result['success']}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to apply plan: {e}")
            raise
    
    async def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        tools_allow: Optional[List[str]] = None,
        mode: str = "auto"
    ) -> AsyncGenerator[str, None]:
        """Streaming chat with tool calling."""
        logger.info(f"Starting chat stream with {len(messages)} messages")
        
        try:
            # Get relevant context from vector index
            last_message = messages[-1]["content"] if messages else ""
            context_results = await self.vector_index.search(last_message, top_k=5)
            
            # Create system prompt
            system_prompt = self._create_chat_system_prompt(tools_allow, mode)
            
            # Prepare messages for LLM
            llm_messages = [
                {"role": "system", "content": system_prompt}
            ] + messages
            
            # Add context from vector search
            if context_results:
                context_message = "Relevant code context:\n" + "\n".join(
                    f"File: {r['path']}\n{r['snippet']}" for r in context_results
                )
                llm_messages.insert(1, {"role": "user", "content": context_message})
            
            # Stream response from LLM
            async for chunk in self.bedrock_client.chat_stream(
                messages=llm_messages,
                tool_schemas=self.tool_schemas if tools_allow else None
            ):
                yield json.dumps(chunk)
                
        except Exception as e:
            logger.error(f"Chat stream failed: {e}")
            yield json.dumps({"error": str(e)})
    
    async def _generate_plan_with_llm(
        self,
        instruction: str,
        mode: str,
        budget: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate plan using LLM."""
        
        # Create system prompt for planning
        system_prompt = self._create_planning_system_prompt(mode, budget)
        
        # Get relevant context from vector index
        context_results = await self.vector_index.search(instruction, top_k=10)
        
        # Create user message
        user_message = f"""Please create a step-by-step plan for the following instruction:

{instruction}

Please provide a detailed plan in the specified JSON format."""

        # Prepare messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        # Add context if available
        if context_results:
            context_text = "Relevant code context:\n" + "\n".join(
                f"File: {r['path']}\n{r['snippet']}" for r in context_results
            )
            messages.insert(1, {"role": "user", "content": context_text})
        
        try:
            # Generate plan using Bedrock
            response = await self.bedrock_client.chat_with_tools(
                messages=messages,
                max_tokens=4000,
                temperature=0.1
            )
            
            # Parse response to extract plan steps
            plan_steps = self._parse_plan_response(response)
            
            return plan_steps
            
        except Exception as e:
            logger.error(f"LLM plan generation failed: {e}")
            # Fallback to simple plan
            return self._create_fallback_plan(instruction)
    
    async def _execute_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single plan step."""
        step_type = step.get("step_type", "tool_call")
        tool_name = step.get("tool_name")
        tool_args = step.get("tool_args", {})
        
        if step_type == "reasoning":
            # Reasoning step - no execution needed
            return {
                "type": "reasoning",
                "description": step.get("description", ""),
                "reasoning": step.get("reasoning", "")
            }
        
        elif step_type == "tool_call" and tool_name:
            # Tool execution step
            return await self._execute_tool(tool_name, tool_args)
        
        else:
            raise ValueError(f"Unknown step type: {step_type}")
    
    async def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific tool."""
        try:
            if tool_name == "read_file":
                result = self.filesystem_tools.read_file(tool_args["path"])
                return {
                    "type": "tool_call",
                    "tool": tool_name,
                    "result": result,
                    "files_affected": [tool_args["path"]]
                }
            
            elif tool_name == "write_file":
                result = self.filesystem_tools.write_file(
                    tool_args["path"],
                    tool_args["content"]
                )
                return {
                    "type": "tool_call",
                    "tool": tool_name,
                    "result": result,
                    "files_affected": [tool_args["path"]]
                }
            
            elif tool_name == "run_command":
                result = await self.command_tools.run_command(
                    tool_args["cmd"],
                    tool_args.get("cwd", ".")
                )
                return {
                    "type": "tool_call",
                    "tool": tool_name,
                    "result": result,
                    "command": {
                        "cmd": tool_args["cmd"],
                        "exit_code": result.get("exit_code")
                    }
                }
            
            elif tool_name == "git_status":
                result = await self.git_tools.git_status()
                return {
                    "type": "tool_call",
                    "tool": tool_name,
                    "result": result
                }
            
            elif tool_name == "git_commit":
                result = await self.git_tools.git_commit(
                    tool_args["message"],
                    tool_args.get("add_all", True)
                )
                return {
                    "type": "tool_call",
                    "tool": tool_name,
                    "result": result
                }
            
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
                
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name} - {e}")
            raise
    
    def _create_planning_system_prompt(self, mode: str, budget: Optional[Dict[str, Any]]) -> str:
        """Create system prompt for planning."""
        
        tool_descriptions = []
        for tool_name, schema in self.tool_schemas.items():
            description = schema.get("description", "")
            # Handle both input_schema and parameters formats
            if "input_schema" in schema:
                properties = schema["input_schema"].get("properties", {})
            else:
                properties = schema.get("parameters", {}).get("properties", {})
            param_list = ", ".join(properties.keys())
            tool_descriptions.append(f"- {tool_name}: {description} (params: {param_list})")
        
        tools_text = "\n".join(tool_descriptions) if tool_descriptions else "No tools available"
        
        budget_text = ""
        if budget:
            steps = budget.get("steps", "unlimited")
            tokens = budget.get("tokens", "unlimited")
            budget_text = f"\n\nBudget constraints:\n- Max steps: {steps}\n- Max tokens: {tokens}"
        
        return f"""You are Zorix Agent — a repository-aware coding agent. Your job is to break down user instructions into a sequence of executable steps using available tools.

Available tools:
{tools_text}
{budget_text}

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
      "step_type": "reasoning" or "tool_call",
      "description": "Clear description of what this step does",
      "tool_name": "tool_to_use" (only for tool_call steps),
      "tool_args": {{"param1": "value1"}} (only for tool_call steps),
      "reasoning": "Why this step is needed",
      "expected_outcome": "What should happen after this step"
    }}
  ]
}}"""
    
    def _create_chat_system_prompt(self, tools_allow: Optional[List[str]], mode: str) -> str:
        """Create system prompt for chat."""
        
        tools_text = "All available tools"
        if tools_allow:
            tools_text = f"Tools: {', '.join(tools_allow)}"
        
        return f"""You are Zorix Agent — a repository-aware coding agent. You can help with code analysis, editing, and execution.

{tools_text}

Guidelines:
1. Stay within the workspace boundaries
2. Use tools when appropriate for file operations or commands
3. Provide clear explanations and examples
4. Respect safety constraints and ask for confirmation for destructive operations
5. Generate code that follows the existing style and patterns"""
    
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
                    "step_type": step.get("step_type", "tool_call"),
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
            raise ValueError(f"Failed to parse plan: {e}")
    
    def _create_fallback_plan(self, instruction: str) -> List[Dict[str, Any]]:
        """Create a simple fallback plan when LLM planning fails."""
        instruction_lower = instruction.lower()
        
        # Email validation specific plan
        if "email" in instruction_lower and ("validate" in instruction_lower or "function" in instruction_lower):
            return [
                {
                    "step_type": "reasoning",
                    "description": "Analyze the requirement for email validation function",
                    "tool_name": None,
                    "tool_args": {},
                    "reasoning": "Need to understand what kind of email validation is required",
                    "expected_outcome": "Clear understanding of the email validation requirements",
                },
                {
                    "step_type": "tool_call",
                    "description": "Create a Python file for the email validation function",
                    "tool_name": "write_file",
                    "tool_args": {"path": "email_validator.py", "content": "# Email validation function will be created here"},
                    "reasoning": "Create a new file to implement the email validation function",
                    "expected_outcome": "New Python file created with placeholder content",
                }
            ]
        
        # Python for loop specific plan
        elif "for loop" in instruction_lower and ("python" in instruction_lower or "code" in instruction_lower):
            return [
                {
                    "step_type": "reasoning",
                    "description": "Analyze the requirement for Python for loop examples",
                    "tool_name": None,
                    "tool_args": {},
                    "reasoning": "Need to understand what kind of for loop examples are needed",
                    "expected_outcome": "Clear understanding of the for loop requirements",
                },
                {
                    "step_type": "tool_call",
                    "description": "Create a Python file with for loop examples",
                    "tool_name": "write_file",
                    "tool_args": {
                        "path": "for_loop_examples.py", 
                        "content": """# Python For Loop Examples

# Basic for loop with range
for i in range(5):
    print(f"Number: {i}")

# For loop with list
fruits = ['apple', 'banana', 'cherry']
for fruit in fruits:
    print(f"I like {fruit}")

# For loop with enumerate
for index, fruit in enumerate(fruits):
    print(f"Index {index}: {fruit}")

# For loop with dictionary
person = {'name': 'John', 'age': 30, 'city': 'New York'}
for key, value in person.items():
    print(f"{key}: {value}")

# For loop with string
for char in "Python":
    print(char)"""
                    },
                    "reasoning": "Create a comprehensive Python file demonstrating various for loop patterns",
                    "expected_outcome": "Python file with multiple for loop examples created",
                }
            ]
        
        # Generic coding task plan
        elif any(word in instruction_lower for word in ["code", "function", "class", "script", "program"]):
            return [
                {
                    "step_type": "reasoning",
                    "description": f"Analyze the coding requirement: {instruction}",
                    "tool_name": None,
                    "tool_args": {},
                    "reasoning": "Need to understand the specific coding requirements",
                    "expected_outcome": "Clear understanding of what needs to be implemented",
                },
                {
                    "step_type": "tool_call",
                    "description": f"Create a Python file for the requested task",
                    "tool_name": "write_file",
                    "tool_args": {
                        "path": "task_implementation.py", 
                        "content": f"# Implementation for: {instruction}\n\n# TODO: Implement the requested functionality here"
                    },
                    "reasoning": "Create a new Python file to implement the requested coding task",
                    "expected_outcome": "Python file created with placeholder for implementation",
                }
            ]
        
        # Generic fallback
        else:
            return [
                {
                    "step_type": "reasoning",
                    "description": f"Execute instruction: {instruction}",
                    "tool_name": None,
                    "tool_args": {},
                    "reasoning": "Fallback plan due to planning failure",
                    "expected_outcome": "Complete the requested task",
                }
            ]
