"""Tests for tool schemas and LLM function calling."""

import pytest

from agent.llm.schemas import (
    get_all_tool_schemas,
    get_analysis_tools_schema,
    get_command_tools_schema,
    get_filesystem_tools_schema,
    get_git_tools_schema,
    get_memory_tools_schema,
    get_system_prompt_with_tools,
    get_tool_names,
    get_tool_schema_by_name,
    validate_tool_call,
)


class TestToolSchemas:
    """Test cases for tool schemas."""
    
    def test_filesystem_tools_schema(self):
        """Test filesystem tools schema structure."""
        schemas = get_filesystem_tools_schema()
        
        # Check that we have the expected tools
        tool_names = [schema["name"] for schema in schemas]
        expected_tools = ["read_file", "write_file", "apply_patch", "list_directory", "search_code"]
        
        for tool in expected_tools:
            assert tool in tool_names
        
        # Check read_file schema structure
        read_file_schema = next(s for s in schemas if s["name"] == "read_file")
        assert "description" in read_file_schema
        assert "input_schema" in read_file_schema
        assert read_file_schema["input_schema"]["type"] == "object"
        assert "path" in read_file_schema["input_schema"]["properties"]
        assert "path" in read_file_schema["input_schema"]["required"]
    
    def test_command_tools_schema(self):
        """Test command tools schema structure."""
        schemas = get_command_tools_schema()
        
        assert len(schemas) == 1
        run_command_schema = schemas[0]
        
        assert run_command_schema["name"] == "run_command"
        assert "description" in run_command_schema
        assert "input_schema" in run_command_schema
        
        properties = run_command_schema["input_schema"]["properties"]
        assert "command" in properties
        assert "working_directory" in properties
        assert "timeout_seconds" in properties
        
        # Check required fields
        required = run_command_schema["input_schema"]["required"]
        assert "command" in required
        assert "working_directory" not in required  # Optional with default
    
    def test_git_tools_schema(self):
        """Test git tools schema structure."""
        schemas = get_git_tools_schema()
        
        tool_names = [schema["name"] for schema in schemas]
        expected_tools = ["git_status", "git_diff", "git_commit", "git_branch", "git_checkout"]
        
        for tool in expected_tools:
            assert tool in tool_names
        
        # Check git_commit schema specifically
        git_commit_schema = next(s for s in schemas if s["name"] == "git_commit")
        properties = git_commit_schema["input_schema"]["properties"]
        required = git_commit_schema["input_schema"]["required"]
        
        assert "message" in properties
        assert "add_all" in properties
        assert "files" in properties
        assert "message" in required
        assert "add_all" not in required  # Optional with default
    
    def test_memory_tools_schema(self):
        """Test memory tools schema structure."""
        schemas = get_memory_tools_schema()
        
        tool_names = [schema["name"] for schema in schemas]
        expected_tools = ["remember_decision", "recall_decision", "get_file_summary"]
        
        for tool in expected_tools:
            assert tool in tool_names
        
        # Check remember_decision schema
        remember_schema = next(s for s in schemas if s["name"] == "remember_decision")
        properties = remember_schema["input_schema"]["properties"]
        required = remember_schema["input_schema"]["required"]
        
        assert "key" in properties
        assert "decision" in properties
        assert "context" in properties
        assert "key" in required
        assert "decision" in required
        assert "context" not in required  # Optional
    
    def test_analysis_tools_schema(self):
        """Test analysis tools schema structure."""
        schemas = get_analysis_tools_schema()
        
        tool_names = [schema["name"] for schema in schemas]
        expected_tools = ["analyze_code_structure", "find_related_files"]
        
        for tool in expected_tools:
            assert tool in tool_names
        
        # Check analyze_code_structure schema
        analyze_schema = next(s for s in schemas if s["name"] == "analyze_code_structure")
        properties = analyze_schema["input_schema"]["properties"]
        
        assert "path" in properties
        assert "include_dependencies" in properties
        assert "max_depth" in properties
        
        # Check constraints
        max_depth_prop = properties["max_depth"]
        assert max_depth_prop["minimum"] == 1
        assert max_depth_prop["maximum"] == 10
    
    def test_get_all_tool_schemas(self):
        """Test getting all tool schemas."""
        all_schemas = get_all_tool_schemas()
        
        # Should include tools from all categories
        tool_names = [schema["name"] for schema in all_schemas]
        
        # Check we have tools from each category
        filesystem_tools = ["read_file", "write_file", "search_code"]
        command_tools = ["run_command"]
        git_tools = ["git_status", "git_commit"]
        memory_tools = ["remember_decision", "recall_decision"]
        analysis_tools = ["analyze_code_structure", "find_related_files"]
        
        for tool in filesystem_tools + command_tools + git_tools + memory_tools + analysis_tools:
            assert tool in tool_names
        
        # Check that each schema has required structure
        for schema in all_schemas:
            assert "name" in schema
            assert "description" in schema
            assert "input_schema" in schema
            assert schema["input_schema"]["type"] == "object"
    
    def test_get_tool_schema_by_name(self):
        """Test getting specific tool schema by name."""
        # Test valid tool
        read_file_schema = get_tool_schema_by_name("read_file")
        assert read_file_schema["name"] == "read_file"
        assert "description" in read_file_schema
        
        # Test invalid tool
        with pytest.raises(ValueError, match="Tool schema not found: invalid_tool"):
            get_tool_schema_by_name("invalid_tool")
    
    def test_get_tool_names(self):
        """Test getting list of tool names."""
        tool_names = get_tool_names()
        
        assert isinstance(tool_names, list)
        assert len(tool_names) > 0
        assert "read_file" in tool_names
        assert "run_command" in tool_names
        assert "git_status" in tool_names
        
        # Check no duplicates
        assert len(tool_names) == len(set(tool_names))
    
    def test_validate_tool_call(self):
        """Test tool call validation."""
        # Valid tool call
        assert validate_tool_call("read_file", {"path": "test.py"}) is True
        
        # Missing required parameter
        assert validate_tool_call("read_file", {}) is False
        
        # Invalid tool name
        assert validate_tool_call("invalid_tool", {"path": "test.py"}) is False
        
        # Valid tool call with optional parameters
        assert validate_tool_call("run_command", {
            "command": "python test.py",
            "working_directory": "src",
            "timeout_seconds": 60
        }) is True
        
        # Valid tool call with only required parameters
        assert validate_tool_call("git_commit", {"message": "Add feature"}) is True
    
    def test_system_prompt_generation(self):
        """Test system prompt generation with tools."""
        prompt = get_system_prompt_with_tools()
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        
        # Check that prompt contains key elements
        assert "Zorix Agent" in prompt
        assert "repository-aware coding assistant" in prompt
        assert "WORKSPACE_ROOT" in prompt
        assert "Available Tools:" in prompt
        
        # Check that some tool names are mentioned
        assert "read_file" in prompt
        assert "run_command" in prompt
        assert "git_status" in prompt
        
        # Check that tool descriptions are included
        assert "Read the contents of a file" in prompt
        assert "Execute a command" in prompt
        
        # Check workflow guidance
        assert "Workflow:" in prompt
        assert "plan" in prompt.lower()
        assert "execute" in prompt.lower()


class TestSchemaValidation:
    """Test schema validation and structure."""
    
    def test_schema_structure_consistency(self):
        """Test that all schemas follow consistent structure."""
        all_schemas = get_all_tool_schemas()
        
        for schema in all_schemas:
            # Required top-level fields
            assert "name" in schema
            assert "description" in schema
            assert "input_schema" in schema
            
            # Name should be non-empty string
            assert isinstance(schema["name"], str)
            assert len(schema["name"]) > 0
            
            # Description should be non-empty string
            assert isinstance(schema["description"], str)
            assert len(schema["description"]) > 0
            
            # Input schema should be valid JSON schema object
            input_schema = schema["input_schema"]
            assert input_schema["type"] == "object"
            assert "properties" in input_schema
            
            # Properties should be a dict
            assert isinstance(input_schema["properties"], dict)
            
            # Required should be a list if present
            if "required" in input_schema:
                assert isinstance(input_schema["required"], list)
                
                # All required fields should exist in properties
                for req_field in input_schema["required"]:
                    assert req_field in input_schema["properties"]
    
    def test_parameter_types_and_constraints(self):
        """Test parameter types and constraints in schemas."""
        all_schemas = get_all_tool_schemas()
        
        for schema in all_schemas:
            properties = schema["input_schema"]["properties"]
            
            for param_name, param_def in properties.items():
                # Each parameter should have a type
                assert "type" in param_def
                
                # Type should be valid JSON schema type
                valid_types = ["string", "integer", "number", "boolean", "array", "object"]
                assert param_def["type"] in valid_types
                
                # If it's an integer/number, check constraints are valid
                if param_def["type"] in ["integer", "number"]:
                    if "minimum" in param_def:
                        assert isinstance(param_def["minimum"], (int, float))
                    if "maximum" in param_def:
                        assert isinstance(param_def["maximum"], (int, float))
                        if "minimum" in param_def:
                            assert param_def["maximum"] >= param_def["minimum"]
                
                # If it's an array, should have items definition
                if param_def["type"] == "array":
                    assert "items" in param_def
                
                # Should have description
                assert "description" in param_def
                assert isinstance(param_def["description"], str)
                assert len(param_def["description"]) > 0
    
    def test_tool_name_uniqueness(self):
        """Test that all tool names are unique."""
        all_schemas = get_all_tool_schemas()
        tool_names = [schema["name"] for schema in all_schemas]
        
        # Check for duplicates
        assert len(tool_names) == len(set(tool_names)), "Tool names must be unique"
    
    def test_required_vs_optional_parameters(self):
        """Test that required/optional parameter handling is correct."""
        # Test a tool with both required and optional parameters
        run_command_schema = get_tool_schema_by_name("run_command")
        properties = run_command_schema["input_schema"]["properties"]
        required = run_command_schema["input_schema"].get("required", [])
        
        # Command should be required
        assert "command" in required
        assert "command" in properties
        
        # Working directory should be optional with default
        assert "working_directory" not in required
        assert "working_directory" in properties
        assert "default" in properties["working_directory"]
        
        # Timeout should be optional with default and constraints
        assert "timeout_seconds" not in required
        assert "timeout_seconds" in properties
        timeout_prop = properties["timeout_seconds"]
        assert "default" in timeout_prop
        assert "minimum" in timeout_prop
        assert "maximum" in timeout_prop


class TestSchemaIntegration:
    """Integration tests for schema usage."""
    
    def test_realistic_tool_calls(self):
        """Test validation of realistic tool call scenarios."""
        # File operations workflow
        file_ops = [
            ("read_file", {"path": "src/main.py"}),
            ("write_file", {"path": "src/new_file.py", "content": "# New file\nprint('hello')"}),
            ("apply_patch", {"path": "src/main.py", "patch": "@@ -1,3 +1,4 @@\n+# Updated\n def main():\n     pass"}),
            ("list_directory", {"path": "src", "pattern": "*.py", "recursive": True}),
            ("search_code", {"query": "def main", "top_k": 10, "file_types": [".py"]}),
        ]
        
        for tool_name, args in file_ops:
            assert validate_tool_call(tool_name, args) is True
        
        # Git operations workflow
        git_ops = [
            ("git_status", {"include_untracked": True}),
            ("git_diff", {"staged": False}),
            ("git_commit", {"message": "Add new feature", "add_all": True}),
            ("git_branch", {"name": "feature-branch"}),
            ("git_checkout", {"ref": "main"}),
        ]
        
        for tool_name, args in git_ops:
            assert validate_tool_call(tool_name, args) is True
        
        # Command execution
        commands = [
            ("run_command", {"command": "python test.py"}),
            ("run_command", {"command": "npm install", "working_directory": "frontend", "timeout_seconds": 120}),
        ]
        
        for tool_name, args in commands:
            assert validate_tool_call(tool_name, args) is True
    
    def test_system_prompt_completeness(self):
        """Test that system prompt includes all necessary information."""
        prompt = get_system_prompt_with_tools()
        all_tool_names = get_tool_names()
        
        # All tools should be mentioned in the prompt
        for tool_name in all_tool_names:
            assert tool_name in prompt, f"Tool {tool_name} not found in system prompt"
        
        # Key concepts should be covered
        key_concepts = [
            "security", "workspace", "plan", "preview", "apply",
            "reasoning", "tools", "workflow", "confirmation"
        ]
        
        for concept in key_concepts:
            assert concept.lower() in prompt.lower(), f"Concept '{concept}' not found in system prompt"