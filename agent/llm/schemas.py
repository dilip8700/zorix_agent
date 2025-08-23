"""Tool schemas for LLM function calling in Zorix Agent."""

from typing import Any, Dict, List

# Tool schemas for AWS Bedrock function calling
# These define the tools available to the LLM for reasoning and action


def get_filesystem_tools_schema() -> List[Dict[str, Any]]:
    """Get schema for filesystem tools."""
    return [
        {
            "name": "read_file",
            "description": "Read the contents of a file from the workspace",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file relative to workspace root"
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "write_file",
            "description": "Write content to a file in the workspace",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file relative to workspace root"
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
            "name": "apply_patch",
            "description": "Apply a unified diff patch to a file",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file relative to workspace root"
                    },
                    "patch": {
                        "type": "string",
                        "description": "Unified diff patch to apply"
                    }
                },
                "required": ["path", "patch"]
            }
        },
        {
            "name": "list_directory",
            "description": "List contents of a directory in the workspace",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the directory relative to workspace root",
                        "default": "."
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to filter files (e.g., '*.py')",
                        "default": "*"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to list files recursively",
                        "default": False
                    }
                },
                "required": []
            }
        },
        {
            "name": "search_code",
            "description": "Search for code patterns or text within the workspace",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query or pattern"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 100
                    },
                    "file_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "File extensions to search (e.g., ['.py', '.js'])"
                    }
                },
                "required": ["query"]
            }
        }
    ]


def get_command_tools_schema() -> List[Dict[str, Any]]:
    """Get schema for command execution tools."""
    return [
        {
            "name": "run_command",
            "description": "Execute a command in the workspace with safety checks",
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to execute (must be in allowlist)"
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Working directory relative to workspace root",
                        "default": "."
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Command timeout in seconds",
                        "default": 90,
                        "minimum": 1,
                        "maximum": 300
                    }
                },
                "required": ["command"]
            }
        }
    ]


def get_git_tools_schema() -> List[Dict[str, Any]]:
    """Get schema for git operation tools."""
    return [
        {
            "name": "git_status",
            "description": "Get the status of the git repository",
            "input_schema": {
                "type": "object",
                "properties": {
                    "include_untracked": {
                        "type": "boolean",
                        "description": "Include untracked files in status",
                        "default": True
                    }
                },
                "required": []
            }
        },
        {
            "name": "git_diff",
            "description": "Get diff of changes in the repository",
            "input_schema": {
                "type": "object",
                "properties": {
                    "revision": {
                        "type": "string",
                        "description": "Revision to diff against (e.g., 'HEAD', 'main')"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Specific file to show diff for"
                    },
                    "staged": {
                        "type": "boolean",
                        "description": "Show only staged changes",
                        "default": False
                    }
                },
                "required": []
            }
        },
        {
            "name": "git_commit",
            "description": "Create a git commit with the specified message",
            "input_schema": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Commit message"
                    },
                    "add_all": {
                        "type": "boolean",
                        "description": "Add all changes before committing",
                        "default": True
                    },
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific files to commit (if not add_all)"
                    }
                },
                "required": ["message"]
            }
        },
        {
            "name": "git_branch",
            "description": "List branches or create a new branch",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of branch to create"
                    },
                    "list_all": {
                        "type": "boolean",
                        "description": "List all branches",
                        "default": False
                    }
                },
                "required": []
            }
        },
        {
            "name": "git_checkout",
            "description": "Checkout a branch, tag, or commit",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ref": {
                        "type": "string",
                        "description": "Branch, tag, or commit hash to checkout"
                    },
                    "create_branch": {
                        "type": "boolean",
                        "description": "Create new branch if it doesn't exist",
                        "default": False
                    }
                },
                "required": ["ref"]
            }
        }
    ]


def get_memory_tools_schema() -> List[Dict[str, Any]]:
    """Get schema for memory and context tools."""
    return [
        {
            "name": "remember_decision",
            "description": "Store a decision or reasoning for future reference",
            "input_schema": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Key to store the decision under"
                    },
                    "decision": {
                        "type": "string",
                        "description": "The decision or reasoning to remember"
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional context about the decision"
                    }
                },
                "required": ["key", "decision"]
            }
        },
        {
            "name": "recall_decision",
            "description": "Retrieve a previously stored decision or reasoning",
            "input_schema": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Key of the decision to retrieve"
                    }
                },
                "required": ["key"]
            }
        },
        {
            "name": "get_file_summary",
            "description": "Get or create a summary of a file's purpose and contents",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file relative to workspace root"
                    },
                    "update": {
                        "type": "boolean",
                        "description": "Force update of existing summary",
                        "default": False
                    }
                },
                "required": ["path"]
            }
        }
    ]


def get_analysis_tools_schema() -> List[Dict[str, Any]]:
    """Get schema for code analysis tools."""
    return [
        {
            "name": "analyze_code_structure",
            "description": "Analyze the structure and dependencies of code files",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to analyze (file or directory)"
                    },
                    "include_dependencies": {
                        "type": "boolean",
                        "description": "Include dependency analysis",
                        "default": True
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth for directory analysis",
                        "default": 3,
                        "minimum": 1,
                        "maximum": 10
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "find_related_files",
            "description": "Find files related to a given file or concept",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reference": {
                        "type": "string",
                        "description": "File path or concept to find related files for"
                    },
                    "relationship_types": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["imports", "exports", "calls", "similar", "tests"]
                        },
                        "description": "Types of relationships to find",
                        "default": ["imports", "calls", "similar"]
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of related files to return",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": ["reference"]
            }
        }
    ]


def get_all_tool_schemas() -> List[Dict[str, Any]]:
    """Get all available tool schemas."""
    schemas = []
    schemas.extend(get_filesystem_tools_schema())
    schemas.extend(get_command_tools_schema())
    schemas.extend(get_git_tools_schema())
    schemas.extend(get_memory_tools_schema())
    schemas.extend(get_analysis_tools_schema())
    return schemas


def get_tool_schema_by_name(tool_name: str) -> Dict[str, Any]:
    """Get a specific tool schema by name."""
    all_schemas = get_all_tool_schemas()
    for schema in all_schemas:
        if schema["name"] == tool_name:
            return schema
    raise ValueError(f"Tool schema not found: {tool_name}")


def get_tool_names() -> List[str]:
    """Get list of all available tool names."""
    return [schema["name"] for schema in get_all_tool_schemas()]


def validate_tool_call(tool_name: str, arguments: Dict[str, Any]) -> bool:
    """Validate a tool call against its schema."""
    try:
        schema = get_tool_schema_by_name(tool_name)
        input_schema = schema["input_schema"]
        
        # Basic validation - check required fields
        required_fields = input_schema.get("required", [])
        for field in required_fields:
            if field not in arguments:
                return False
        
        # Type validation would go here in a full implementation
        # For now, just check that required fields are present
        return True
        
    except ValueError:
        return False


def get_system_prompt_with_tools() -> str:
    """Get system prompt that includes tool descriptions."""
    tool_descriptions = []
    
    for schema in get_all_tool_schemas():
        name = schema["name"]
        description = schema["description"]
        properties = schema["input_schema"].get("properties", {})
        required = schema["input_schema"].get("required", [])
        
        param_desc = []
        for param, details in properties.items():
            param_type = details.get("type", "string")
            param_desc_text = details.get("description", "")
            is_required = param in required
            req_marker = " (required)" if is_required else " (optional)"
            param_desc.append(f"  - {param} ({param_type}){req_marker}: {param_desc_text}")
        
        tool_desc = f"**{name}**: {description}\nParameters:\n" + "\n".join(param_desc)
        tool_descriptions.append(tool_desc)
    
    tools_text = "\n\n".join(tool_descriptions)
    
    return f"""You are Zorix Agent, a repository-aware coding assistant. You help developers by understanding their codebase, planning multi-step tasks, and executing safe file operations, command execution, and git operations.

## Core Principles:
- Stay within the WORKSPACE_ROOT directory at all times for security
- Respect the plan/preview/apply workflow for changes
- Maintain coding style and generate diffs, not prose
- Ask for confirmation before destructive operations
- Be minimal and deterministic in your responses
- All operations are sandboxed within the workspace for security

## Available Tools:
{tools_text}

## Workflow:
1. Understand the user's request
2. Search and analyze relevant code if needed
3. Plan the necessary steps with preview of changes
4. Execute tools to apply changes safely
5. Verify results and provide summary

Always explain your reasoning and what you're doing at each step. Request confirmation for any potentially destructive operations."""