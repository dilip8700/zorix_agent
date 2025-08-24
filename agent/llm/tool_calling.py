"""Tool calling validation and execution for LLM orchestrator."""

import asyncio
import logging
from typing import Any, Dict, Optional

from agent.llm.schemas import get_tool_schema_by_name, validate_tool_call as validate_schema
from agent.tools.filesystem import FilesystemTools
from agent.tools.command import CommandTools
from agent.tools.git import GitTools

logger = logging.getLogger(__name__)


def validate_tool_call(tool_name: str, arguments: Dict[str, Any]) -> bool:
    """Validate a tool call against its schema.
    
    Args:
        tool_name: Name of the tool
        arguments: Tool arguments
        
    Returns:
        True if valid
    """
    try:
        return validate_schema(tool_name, arguments)
    except Exception as e:
        logger.error(f"Tool validation failed for {tool_name}: {e}")
        return False


async def execute_tool_call(
    tool_name: str,
    arguments: Dict[str, Any],
    workspace_root: Optional[str] = None
) -> Any:
    """Execute a tool call.
    
    Args:
        tool_name: Name of the tool to execute
        arguments: Tool arguments
        workspace_root: Workspace root directory
        
    Returns:
        Tool execution result
        
    Raises:
        ValueError: If tool is unknown or execution fails
    """
    logger.info(f"Executing tool: {tool_name} with args: {arguments}")
    
    # Initialize tools
    filesystem_tools = FilesystemTools(workspace_root=workspace_root)
    command_tools = CommandTools(workspace_root=workspace_root)
    git_tools = GitTools(workspace_root=workspace_root)
    
    # Tool dispatch
    try:
        if tool_name == "read_file":
            return await _execute_async(filesystem_tools.read_file, **arguments)
        
        elif tool_name == "write_file":
            return await _execute_async(filesystem_tools.write_file, **arguments)
        
        elif tool_name == "apply_patch":
            return await _execute_async(filesystem_tools.apply_patch, **arguments)
        
        elif tool_name == "list_directory":
            return await _execute_async(filesystem_tools.list_directory, **arguments)
        
        elif tool_name == "search_code":
            return await _execute_async(filesystem_tools.search_code, **arguments)
        
        elif tool_name == "run_command":
            return await _execute_async(command_tools.run_command, **arguments)
        
        elif tool_name == "git_status":
            return await _execute_async(git_tools.git_status, **arguments)
        
        elif tool_name == "git_diff":
            return await _execute_async(git_tools.git_diff, **arguments)
        
        elif tool_name == "git_commit":
            return await _execute_async(git_tools.git_commit, **arguments)
        
        elif tool_name == "git_branch":
            return await _execute_async(git_tools.git_branch, **arguments)
        
        elif tool_name == "git_checkout":
            return await _execute_async(git_tools.git_checkout, **arguments)
        
        elif tool_name == "git_add":
            return await _execute_async(git_tools.git_add, **arguments)
        
        elif tool_name == "git_reset":
            return await _execute_async(git_tools.git_reset, **arguments)
        
        elif tool_name == "git_log":
            return await _execute_async(git_tools.git_log, **arguments)
        
        elif tool_name == "remember_decision":
            return await _execute_memory_tool("remember", arguments)
        
        elif tool_name == "recall_decision":
            return await _execute_memory_tool("recall", arguments)
        
        elif tool_name == "get_file_summary":
            return await _execute_memory_tool("summarize", arguments)
        
        elif tool_name == "analyze_code_structure":
            return await _execute_analysis_tool("structure", arguments, filesystem_tools)
        
        elif tool_name == "find_related_files":
            return await _execute_analysis_tool("related", arguments, filesystem_tools)
        
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    except Exception as e:
        logger.error(f"Tool execution failed for {tool_name}: {e}")
        raise ValueError(f"Tool execution failed: {str(e)}") from e


async def _execute_async(func, **kwargs):
    """Execute a function asynchronously if needed."""
    if asyncio.iscoroutinefunction(func):
        return await func(**kwargs)
    else:
        # Run in thread pool for sync functions
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(**kwargs))


async def _execute_memory_tool(operation: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute memory-related tools."""
    # Placeholder implementation
    # In a full implementation, this would interact with the memory provider
    
    if operation == "remember":
        key = arguments.get("key", "")
        decision = arguments.get("decision", "")
        context = arguments.get("context", "")
        
        return {
            "success": True,
            "message": f"Remembered decision for key: {key}",
            "key": key,
            "decision": decision,
            "context": context
        }
    
    elif operation == "recall":
        key = arguments.get("key", "")
        
        return {
            "success": True,
            "key": key,
            "decision": f"Recalled decision for {key}",
            "context": "Previously stored context"
        }
    
    elif operation == "summarize":
        path = arguments.get("path", "")
        
        return {
            "success": True,
            "path": path,
            "summary": f"File summary for {path}",
            "last_updated": "recent"
        }
    
    else:
        raise ValueError(f"Unknown memory operation: {operation}")


async def _execute_analysis_tool(
    analysis_type: str,
    arguments: Dict[str, Any],
    filesystem_tools: FilesystemTools
) -> Dict[str, Any]:
    """Execute code analysis tools."""
    
    if analysis_type == "structure":
        path = arguments.get("path", ".")
        include_dependencies = arguments.get("include_dependencies", True)
        max_depth = arguments.get("max_depth", 3)
        
        try:
            # Get directory listing
            listing = await _execute_async(
                filesystem_tools.list_directory,
                path=path,
                recursive=True
            )
            
            # Analyze structure
            files = [item for item in listing.get("entries", []) if not item.get("is_directory")]
            directories = [item for item in listing.get("entries", []) if item.get("is_directory")]
            
            # Group by file type
            file_types = {}
            for file_info in files:
                ext = file_info.get("path", "").split(".")[-1] if "." in file_info.get("path", "") else "no_ext"
                if ext not in file_types:
                    file_types[ext] = 0
                file_types[ext] += 1
            
            return {
                "path": path,
                "total_files": len(files),
                "total_directories": len(directories),
                "file_types": file_types,
                "structure": {
                    "files": files[:20],  # Limit to first 20 files
                    "directories": directories[:10]  # Limit to first 10 directories
                },
                "include_dependencies": include_dependencies,
                "max_depth": max_depth
            }
            
        except Exception as e:
            return {
                "error": f"Failed to analyze structure: {str(e)}",
                "path": path
            }
    
    elif analysis_type == "related":
        reference = arguments.get("reference", "")
        relationship_types = arguments.get("relationship_types", ["imports", "calls", "similar"])
        max_results = arguments.get("max_results", 10)
        
        try:
            # Search for related files
            search_results = await _execute_async(
                filesystem_tools.search_code,
                query=reference,
                top_k=max_results
            )
            
            # Process results based on relationship types
            related_files = []
            for result in search_results.get("results", []):
                related_files.append({
                    "path": result.get("path"),
                    "relationship": "similar",  # Simplified for now
                    "score": result.get("score", 0.0),
                    "snippet": result.get("snippet", "")[:100] + "..."
                })
            
            return {
                "reference": reference,
                "relationship_types": relationship_types,
                "related_files": related_files,
                "total_found": len(related_files)
            }
            
        except Exception as e:
            return {
                "error": f"Failed to find related files: {str(e)}",
                "reference": reference
            }
    
    else:
        raise ValueError(f"Unknown analysis type: {analysis_type}")