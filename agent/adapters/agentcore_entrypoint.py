"""
AgentCore Runtime Adapter for Zorix Agent

This module provides a drop-in adapter to run Zorix Agent inside 
Amazon Bedrock AgentCore Runtime without requiring code refactoring.
"""

import logging
import os
from typing import Any, Dict, Optional

from agent.config import get_settings
from agent.web.api import create_app

logger = logging.getLogger(__name__)


# AgentCore Gateway Tools registration
GATEWAY_TOOLS = [
    {
        "name": "read_file",
        "description": "Read contents of a file in the workspace",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file", 
        "description": "Write content to a file in the workspace",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "run_command",
        "description": "Execute a safe command in the workspace",
        "parameters": {
            "type": "object", 
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command to execute"
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory (optional)"
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "git_status",
        "description": "Get git repository status",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "git_commit",
        "description": "Commit changes to git repository",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Commit message"
                },
                "add_all": {
                    "type": "boolean",
                    "description": "Add all files before committing"
                }
            },
            "required": ["message"]
        }
    },
    {
        "name": "search_code",
        "description": "Search for code patterns in the workspace",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of results"
                }
            },
            "required": ["query"]
        }
    }
]


def get_gateway_tool_definitions() -> list[Dict[str, Any]]:
    """Get tool definitions for AgentCore Gateway registration."""
    return GATEWAY_TOOLS


class AgentCoreAdapter:
    """Adapter for running Zorix Agent in AgentCore Runtime."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the adapter.
        
        Args:
            config: Optional configuration overrides
        """
        self.config = config or {}
        self.app = None
        self.settings = None
        
        # Configure environment for AgentCore
        self._configure_agentcore_environment()
        
        logger.info("AgentCore adapter initialized")
    
    def _configure_agentcore_environment(self):
        """Configure environment variables for AgentCore deployment."""
        
        # Set default AgentCore-specific settings
        agentcore_defaults = {
            "WORKSPACE_ROOT": "/tmp/agentcore_workspace",
            "APP_PORT": "8080",  # AgentCore standard port
            "BEDROCK_REGION": os.getenv("AWS_REGION", "us-east-1"),
            "LOG_LEVEL": "INFO",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "",  # Disable OTEL in AgentCore by default
        }
        
        # Apply defaults only if not already set
        for key, value in agentcore_defaults.items():
            if key not in os.environ:
                os.environ[key] = value
        
        # Override with adapter config
        for key, value in self.config.items():
            env_key = key.upper()
            os.environ[env_key] = str(value)
        
        logger.info("AgentCore environment configured")
    
    async def initialize(self):
        """Initialize the Zorix Agent for AgentCore runtime."""
        try:
            # Get settings with AgentCore overrides
            self.settings = get_settings()
            
            # Create the FastAPI app
            self.app = create_app()
            
            # Register tools with AgentCore Gateway (stub implementation)
            await self._register_gateway_tools()
            
            logger.info("Zorix Agent initialized for AgentCore")
            return self.app
            
        except Exception as e:
            logger.error(f"Failed to initialize AgentCore adapter: {e}")
            raise
    
    async def _register_gateway_tools(self):
        """Register tools with AgentCore Gateway (stub implementation).
        
        In a real AgentCore deployment, this would register tools
        with the Gateway service for external access.
        """
        tool_count = len(GATEWAY_TOOLS)
        logger.info(f"Would register {tool_count} tools with AgentCore Gateway")
        
        # Stub: In real implementation, this would make API calls to
        # the AgentCore Gateway service to register each tool
        for tool in GATEWAY_TOOLS:
            logger.debug(f"Registering tool: {tool['name']}")
        
        logger.info("Tools registered with AgentCore Gateway")
    
    async def handle_agentcore_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming AgentCore requests.
        
        This method processes requests from the AgentCore runtime
        and routes them to appropriate Zorix Agent functionality.
        
        Args:
            request: AgentCore request payload
            
        Returns:
            Response payload for AgentCore
        """
        try:
            request_type = request.get("type", "unknown")
            
            if request_type == "tool_call":
                return await self._handle_tool_call(request)
            elif request_type == "chat":
                return await self._handle_chat(request)
            elif request_type == "plan":
                return await self._handle_plan(request)
            else:
                logger.warning(f"Unknown request type: {request_type}")
                return {
                    "success": False,
                    "error": f"Unknown request type: {request_type}"
                }
                
        except Exception as e:
            logger.error(f"Error handling AgentCore request: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _handle_tool_call(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tool call requests from AgentCore."""
        tool_name = request.get("tool_name")
        arguments = request.get("arguments", {})
        
        logger.info(f"Handling tool call: {tool_name}")
        
        # Import here to avoid circular imports
        from agent.llm.tool_calling import execute_tool_call
        
        try:
            result = await execute_tool_call(
                tool_name=tool_name,
                arguments=arguments,
                workspace_root=self.settings.workspace_root
            )
            
            return {
                "success": True,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Tool call failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _handle_chat(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle chat requests from AgentCore."""
        message = request.get("message", "")
        mode = request.get("mode", "create")
        
        logger.info(f"Handling chat request: {message[:50]}...")
        
        # Import here to avoid circular imports
        from agent.web.api import get_app_state
        
        try:
            app_state = get_app_state()
            orchestrator = app_state.get("llm_orchestrator")
            
            if not orchestrator:
                return {
                    "success": False,
                    "error": "LLM orchestrator not available"
                }
            
            # Process chat message
            from agent.models.base import Message, MessageRole
            
            message_obj = Message(role=MessageRole.USER, content=message)
            
            # Get response (non-streaming for AgentCore)
            response_chunks = []
            async for chunk in orchestrator.chat_with_tools(
                messages=[message_obj],
                mode=mode,
                stream=False
            ):
                if chunk.get("type") == "message_complete":
                    return {
                        "success": True,
                        "response": chunk.get("content", ""),
                        "metadata": chunk
                    }
                response_chunks.append(chunk)
            
            # Fallback if no complete message
            return {
                "success": True,
                "response": "Response received but incomplete",
                "metadata": {"chunks": response_chunks}
            }
            
        except Exception as e:
            logger.error(f"Chat request failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _handle_plan(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle planning requests from AgentCore."""
        instruction = request.get("instruction", "")
        mode = request.get("mode", "edit")
        
        logger.info(f"Handling plan request: {instruction[:50]}...")
        
        # Import here to avoid circular imports
        from agent.web.api import get_app_state
        
        try:
            app_state = get_app_state()
            orchestrator = app_state.get("llm_orchestrator")
            
            if not orchestrator:
                return {
                    "success": False,
                    "error": "LLM orchestrator not available"
                }
            
            # Create plan
            plan_result = await orchestrator.plan_task(
                instruction=instruction,
                mode=mode
            )
            
            return {
                "success": True,
                "plan": plan_result
            }
            
        except Exception as e:
            logger.error(f"Plan request failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_asgi_app(self):
        """Get the ASGI application for AgentCore deployment."""
        if not self.app:
            raise RuntimeError("Adapter not initialized. Call initialize() first.")
        return self.app


# AgentCore entrypoint function
async def agentcore_entrypoint(config: Optional[Dict[str, Any]] = None):
    """
    Main entrypoint for AgentCore Runtime deployment.
    
    This function is called by the AgentCore runtime to initialize
    and mount the Zorix Agent service.
    
    Args:
        config: Optional configuration overrides
        
    Returns:
        ASGI application ready for AgentCore deployment
    """
    logger.info("Starting Zorix Agent in AgentCore Runtime")
    
    adapter = AgentCoreAdapter(config)
    app = await adapter.initialize()
    
    logger.info("Zorix Agent ready for AgentCore Runtime")
    
    return app


# For backward compatibility and direct usage
adapter_instance = None

def get_adapter_instance() -> AgentCoreAdapter:
    """Get the global adapter instance."""
    global adapter_instance
    if adapter_instance is None:
        adapter_instance = AgentCoreAdapter()
    return adapter_instance


# Export the main entrypoint for AgentCore
__all__ = [
    "agentcore_entrypoint",
    "AgentCoreAdapter", 
    "get_gateway_tool_definitions",
    "get_adapter_instance",
    "GATEWAY_TOOLS"
]
