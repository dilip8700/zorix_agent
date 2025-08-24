"""
AgentCore Gateway Tools Registration

Stubs for registering Zorix Agent tools with the AgentCore Gateway service.
This module provides the interface for external tool access in AgentCore deployments.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GatewayToolsRegistry:
    """Registry for AgentCore Gateway tools."""
    
    def __init__(self, gateway_endpoint: Optional[str] = None):
        """Initialize the registry.
        
        Args:
            gateway_endpoint: AgentCore Gateway API endpoint
        """
        self.gateway_endpoint = gateway_endpoint
        self.registered_tools: Dict[str, Dict[str, Any]] = {}
        
        logger.info("Gateway tools registry initialized")
    
    async def register_tool(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler_endpoint: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Register a tool with the AgentCore Gateway.
        
        Args:
            name: Tool name
            description: Tool description
            parameters: JSON schema for tool parameters
            handler_endpoint: Endpoint that handles this tool
            metadata: Additional tool metadata
            
        Returns:
            True if registration successful
        """
        tool_definition = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "handler_endpoint": handler_endpoint,
            "metadata": metadata or {}
        }
        
        logger.info(f"Registering tool: {name}")
        
        # In a real implementation, this would make an API call to
        # the AgentCore Gateway service
        if self.gateway_endpoint:
            success = await self._make_gateway_request("register", tool_definition)
            if success:
                self.registered_tools[name] = tool_definition
                logger.info(f"Tool {name} registered successfully")
                return True
            else:
                logger.error(f"Failed to register tool {name}")
                return False
        else:
            # Stub mode - just store locally
            self.registered_tools[name] = tool_definition
            logger.info(f"Tool {name} registered locally (stub mode)")
            return True
    
    async def unregister_tool(self, name: str) -> bool:
        """Unregister a tool from the Gateway.
        
        Args:
            name: Tool name to unregister
            
        Returns:
            True if unregistration successful
        """
        if name not in self.registered_tools:
            logger.warning(f"Tool {name} not found in registry")
            return False
        
        logger.info(f"Unregistering tool: {name}")
        
        if self.gateway_endpoint:
            success = await self._make_gateway_request("unregister", {"name": name})
            if success:
                del self.registered_tools[name]
                logger.info(f"Tool {name} unregistered successfully")
                return True
            else:
                logger.error(f"Failed to unregister tool {name}")
                return False
        else:
            # Stub mode
            del self.registered_tools[name]
            logger.info(f"Tool {name} unregistered locally (stub mode)")
            return True
    
    async def register_all_zorix_tools(self, base_endpoint: str) -> bool:
        """Register all Zorix Agent tools with the Gateway.
        
        Args:
            base_endpoint: Base endpoint for tool handlers
            
        Returns:
            True if all tools registered successfully
        """
        from .agentcore_entrypoint import GATEWAY_TOOLS
        
        logger.info(f"Registering {len(GATEWAY_TOOLS)} Zorix tools")
        
        success_count = 0
        for tool in GATEWAY_TOOLS:
            handler_endpoint = f"{base_endpoint}/tools/{tool['name']}"
            
            success = await self.register_tool(
                name=tool["name"],
                description=tool["description"],
                parameters=tool["parameters"],
                handler_endpoint=handler_endpoint,
                metadata={"source": "zorix-agent", "version": "1.0.0"}
            )
            
            if success:
                success_count += 1
        
        logger.info(f"Registered {success_count}/{len(GATEWAY_TOOLS)} tools")
        return success_count == len(GATEWAY_TOOLS)
    
    async def _make_gateway_request(self, action: str, data: Dict[str, Any]) -> bool:
        """Make a request to the AgentCore Gateway service.
        
        This is a stub implementation. In a real deployment, this would
        make HTTP requests to the Gateway service.
        
        Args:
            action: Gateway action (register/unregister)
            data: Request payload
            
        Returns:
            True if request successful
        """
        logger.debug(f"Gateway request: {action} with data: {data}")
        
        # Stub implementation - always returns success
        # In real implementation:
        # 1. Make HTTP request to self.gateway_endpoint
        # 2. Handle authentication/authorization
        # 3. Parse response and handle errors
        # 4. Return actual success status
        
        return True
    
    def get_registered_tools(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered tools.
        
        Returns:
            Dictionary of registered tools
        """
        return self.registered_tools.copy()
    
    def is_tool_registered(self, name: str) -> bool:
        """Check if a tool is registered.
        
        Args:
            name: Tool name
            
        Returns:
            True if tool is registered
        """
        return name in self.registered_tools


# Global registry instance
_registry_instance: Optional[GatewayToolsRegistry] = None


def get_gateway_registry(gateway_endpoint: Optional[str] = None) -> GatewayToolsRegistry:
    """Get the global gateway tools registry.
    
    Args:
        gateway_endpoint: Gateway endpoint (only used on first call)
        
    Returns:
        Gateway tools registry instance
    """
    global _registry_instance
    
    if _registry_instance is None:
        _registry_instance = GatewayToolsRegistry(gateway_endpoint)
    
    return _registry_instance


async def register_zorix_tools_with_gateway(
    base_endpoint: str,
    gateway_endpoint: Optional[str] = None
) -> bool:
    """Convenience function to register all Zorix tools.
    
    Args:
        base_endpoint: Base endpoint for tool handlers
        gateway_endpoint: Gateway service endpoint
        
    Returns:
        True if all tools registered successfully
    """
    registry = get_gateway_registry(gateway_endpoint)
    return await registry.register_all_zorix_tools(base_endpoint)


# Tool handler endpoint stubs
async def handle_tool_request(tool_name: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle a tool request from the Gateway.
    
    This function receives tool execution requests from the AgentCore Gateway
    and routes them to the appropriate Zorix Agent tool handlers.
    
    Args:
        tool_name: Name of the tool to execute
        request_data: Tool execution parameters
        
    Returns:
        Tool execution result
    """
    logger.info(f"Handling Gateway tool request: {tool_name}")
    
    try:
        from agent.llm.tool_calling import execute_tool_call
        from agent.config import get_settings
        
        settings = get_settings()
        
        # Extract arguments from request
        arguments = request_data.get("arguments", {})
        
        # Execute the tool
        result = await execute_tool_call(
            tool_name=tool_name,
            arguments=arguments,
            workspace_root=settings.workspace_root
        )
        
        return {
            "success": True,
            "result": result,
            "tool_name": tool_name
        }
        
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "tool_name": tool_name
        }


__all__ = [
    "GatewayToolsRegistry",
    "get_gateway_registry", 
    "register_zorix_tools_with_gateway",
    "handle_tool_request"
]
