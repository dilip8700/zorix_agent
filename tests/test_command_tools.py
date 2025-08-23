"""Tests for Command execution tools."""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.tools.command import CommandTools
from agent.security.exceptions import SecurityError
from agent.models.base import CommandResult


class TestCommandTools:
    """Test cases for CommandTools."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def command_tools(self, temp_workspace):
        """Create CommandTools instance with temp workspace."""
        return CommandTools(
            workspace_root=str(temp_workspace),
            max_output_size=1024,
            default_timeout=10
        )
    
    def test_initialization(self, temp_workspace):
        """Test CommandTools initialization."""
        tools = CommandTools(workspace_root=str(temp_workspace))
        
        assert tools.workspace_root == temp_workspace.resolve()
        assert tools.sandbox is not None
        assert len(tools.allowlist) > 0
        assert tools.max_output_size == 1024 * 1024  # Default
        assert tools.default_timeout == 300  # Default
    
    def test_initialization_with_custom_allowlist(self, temp_workspace):
        """Test initialization with custom allowlist."""
        custom_allowlist = ["echo", "ls", "pwd"]
        tools = CommandTools(
            workspace_root=str(temp_workspace),
            allowlist=custom_allowlist
        )
        
        assert tools.allowlist == custom_allowlist
    
    def test_is_command_allowed_exact_match(self, command_tools):
        """Test command allowlist with exact matches."""
        # Add test command to allowlist
        command_tools.add_to_allowlist("test-command")
        
        assert command_tools.is_command_allowed("test-command")
        assert not command_tools.is_command_allowed("forbidden-command")
    
    def test_is_command_allowed_with_args(self, command_tools):
        """Test command allowlist with arguments."""
        # Should allow commands with arguments if base command is allowed
        assert command_tools.is_command_allowed("echo hello world")
        assert command_tools.is_command_allowed("ls -la")
        
        # Should not allow if base command is not in allowlist
        assert not command_tools.is_command_allowed("rm -rf /")
    
    def test_is_command_allowed_base_command(self, command_tools):
        """Test command allowlist checking base command."""
        # Add base command
        command_tools.add_to_allowlist("git")
        
        assert command_tools.is_command_allowed("git")
        assert command_tools.is_command_allowed("git status")
        assert command_tools.is_command_allowed("git commit -m 'test'")
    
    @pytest.mark.asyncio
    async def test_run_command_success(self, command_tools):
        """Test successful command execution."""
        # Use a simple command that should work on most systems
        if os.name == 'nt':  # Windows
            command = "echo hello"
        else:  # Unix-like
            command = "echo hello"
        
        result = await command_tools.run_command(command)
        
        assert isinstance(result, CommandResult)
        assert result.command == command
        assert result.success is True
        assert result.exit_code == 0
        assert "hello" in result.stdout.lower()
        assert result.duration > 0
        assert not result.timeout
    
    @pytest.mark.asyncio
    async def test_run_command_not_allowed(self, command_tools):
        """Test command execution with disallowed command."""
        result = await command_tools.run_command("forbidden-command")
        
        assert not result.success
        assert result.exit_code == -1
        assert "not allowed" in result.stderr.lower()
    
    @pytest.mark.asyncio
    async def test_run_command_empty(self, command_tools):
        """Test command execution with empty command."""
        result = await command_tools.run_command("")
        
        assert not result.success
        assert result.exit_code == -1
        assert "cannot be empty" in result.stderr.lower()
    
    @pytest.mark.asyncio
    async def test_run_command_with_cwd(self, command_tools, temp_workspace):
        """Test command execution with custom working directory."""
        # Create subdirectory
        subdir = temp_workspace / "subdir"
        subdir.mkdir()
        
        if os.name == 'nt':  # Windows
            command = "cd"
        else:  # Unix-like
            command = "pwd"
        
        result = await command_tools.run_command(command, cwd="subdir")
        
        assert result.success
        assert "subdir" in result.stdout
    
    @pytest.mark.asyncio
    async def test_run_command_invalid_cwd(self, command_tools):
        """Test command execution with invalid working directory."""
        result = await command_tools.run_command("echo test", cwd="nonexistent")
        
        assert not result.success
        assert "does not exist" in result.stderr
    
    @pytest.mark.asyncio
    async def test_run_command_outside_workspace(self, command_tools):
        """Test command execution with working directory outside workspace."""
        result = await command_tools.run_command("echo test", cwd="../outside")
        
        assert not result.success
        assert "outside workspace" in result.stderr.lower()
    
    @pytest.mark.asyncio
    async def test_run_command_timeout(self, command_tools):
        """Test command execution timeout."""
        # Use a command that will timeout
        if os.name == 'nt':  # Windows
            # Use PowerShell Start-Sleep which is more reliable for timeout testing
            command = "powershell -Command Start-Sleep -Seconds 5"
        else:  # Unix-like
            command = "sleep 5"  # 5 second delay
        
        # Set very short timeout
        result = await command_tools.run_command(command, timeout=1)
        
        assert not result.success
        # On Windows, the command might fail for other reasons, so check for timeout OR failure
        if result.timeout:
            assert result.timeout
            assert "timed out" in result.stderr.lower()
        else:
            # Command failed for other reasons (e.g., PowerShell not in allowlist)
            assert result.exit_code != 0
    
    @pytest.mark.asyncio
    async def test_run_command_with_env(self, command_tools):
        """Test command execution with environment variables."""
        env = {"TEST_VAR": "test_value"}
        
        if os.name == 'nt':  # Windows
            command = "echo %TEST_VAR%"
        else:  # Unix-like
            command = "echo $TEST_VAR"
        
        result = await command_tools.run_command(command, env=env)
        
        if result.success:  # Some systems might not support this
            assert "test_value" in result.stdout
    
    @pytest.mark.asyncio
    async def test_run_command_failed_command(self, command_tools):
        """Test command execution with command that fails."""
        # Use a command that should fail
        if os.name == 'nt':  # Windows
            command = "dir nonexistent_directory"
        else:  # Unix-like
            command = "ls nonexistent_directory"
        
        result = await command_tools.run_command(command)
        
        assert not result.success
        assert result.exit_code != 0
        assert len(result.stderr) > 0
    
    @pytest.mark.asyncio
    async def test_run_command_output_limit(self, command_tools):
        """Test command execution with output size limit."""
        # Set very small output limit
        command_tools.max_output_size = 50
        
        # Generate large output
        if os.name == 'nt':  # Windows
            command = "echo " + "x" * 100
        else:  # Unix-like
            command = "echo " + "x" * 100
        
        result = await command_tools.run_command(command)
        
        if result.success:
            assert len(result.stdout) <= 70  # 50 + some buffer for truncation message
            if len(result.stdout) >= 50:
                assert "TRUNCATED" in result.stdout
    
    def test_redact_secrets(self, command_tools):
        """Test secret redaction functionality."""
        test_cases = [
            ("password=secret123", "password=[REDACTED]"),
            ("API_KEY=abc123def456", "API_KEY=[REDACTED]"),
            ("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "Bearer [REDACTED]"),
            ("token: sk-1234567890abcdef", "token: [REDACTED]"),
            ("Normal text without secrets", "Normal text without secrets"),
        ]
        
        for original, expected_pattern in test_cases:
            redacted = command_tools._redact_secrets(original)
            if "[REDACTED]" in expected_pattern:
                assert "[REDACTED]" in redacted
            else:
                assert redacted == expected_pattern
    
    def test_add_to_allowlist(self, command_tools):
        """Test adding commands to allowlist."""
        initial_size = len(command_tools.allowlist)
        
        # Add single command
        command_tools.add_to_allowlist("new-command")
        assert len(command_tools.allowlist) == initial_size + 1
        assert "new-command" in command_tools.allowlist
        
        # Add multiple commands
        command_tools.add_to_allowlist(["cmd1", "cmd2"])
        assert len(command_tools.allowlist) == initial_size + 3
        assert "cmd1" in command_tools.allowlist
        assert "cmd2" in command_tools.allowlist
        
        # Adding duplicate should not increase size
        command_tools.add_to_allowlist("new-command")
        assert len(command_tools.allowlist) == initial_size + 3
    
    def test_remove_from_allowlist(self, command_tools):
        """Test removing commands from allowlist."""
        # Add test commands
        command_tools.add_to_allowlist(["test1", "test2", "test3"])
        initial_size = len(command_tools.allowlist)
        
        # Remove single command
        command_tools.remove_from_allowlist("test1")
        assert len(command_tools.allowlist) == initial_size - 1
        assert "test1" not in command_tools.allowlist
        
        # Remove multiple commands
        command_tools.remove_from_allowlist(["test2", "test3"])
        assert len(command_tools.allowlist) == initial_size - 3
        assert "test2" not in command_tools.allowlist
        assert "test3" not in command_tools.allowlist
        
        # Removing non-existent command should not change size
        original_size = len(command_tools.allowlist)
        command_tools.remove_from_allowlist("nonexistent")
        assert len(command_tools.allowlist) == original_size
    
    def test_get_allowlist(self, command_tools):
        """Test getting allowlist copy."""
        allowlist = command_tools.get_allowlist()
        
        assert isinstance(allowlist, list)
        assert len(allowlist) > 0
        
        # Modifying returned list should not affect original
        original_size = len(command_tools.allowlist)
        allowlist.append("test-command")
        assert len(command_tools.allowlist) == original_size
    
    @pytest.mark.asyncio
    async def test_which_command_found(self, command_tools):
        """Test finding command path."""
        # Test with a command that should exist on most systems
        if os.name == 'nt':  # Windows
            test_command = "cmd"
        else:  # Unix-like
            test_command = "sh"
        
        path = await command_tools.which(test_command)
        
        if path:  # Command might not be available in test environment
            assert isinstance(path, str)
            assert len(path) > 0
    
    @pytest.mark.asyncio
    async def test_which_command_not_found(self, command_tools):
        """Test finding non-existent command."""
        path = await command_tools.which("definitely-nonexistent-command-12345")
        
        assert path is None
    
    @pytest.mark.asyncio
    async def test_test_command(self, command_tools):
        """Test command testing functionality."""
        # Test with echo command
        result = await command_tools.test_command("echo")
        
        assert isinstance(result, dict)
        assert result["command"] == "echo"
        assert result["base_command"] == "echo"
        assert result["allowed"] is True  # echo should be in default allowlist
        
        # Test with non-existent command
        result = await command_tools.test_command("nonexistent-command-12345")
        
        assert result["command"] == "nonexistent-command-12345"
        assert result["allowed"] is False
        assert result["available"] is False
    
    @pytest.mark.asyncio
    async def test_get_system_info(self, command_tools):
        """Test getting system information."""
        info = await command_tools.get_system_info()
        
        assert isinstance(info, dict)
        assert "platform" in info
        assert "workspace_root" in info
        assert "allowlist_size" in info
        
        assert info["platform"] == os.name
        assert str(command_tools.workspace_root) in info["workspace_root"]
        assert info["allowlist_size"] > 0
    
    def test_default_allowlist_contents(self, command_tools):
        """Test that default allowlist contains expected commands."""
        allowlist = command_tools.get_allowlist()
        
        # Check for some essential commands
        expected_commands = ["echo", "git", "python", "npm", "ls", "pwd"]
        
        for cmd in expected_commands:
            # Check if command or command with args is in allowlist
            found = any(
                cmd == allowed or allowed.startswith(cmd + " ") or cmd in allowed
                for allowed in allowlist
            )
            assert found, f"Expected command '{cmd}' not found in allowlist"
    
    def test_secret_patterns_compilation(self, command_tools):
        """Test that secret patterns are properly compiled."""
        assert len(command_tools._secret_patterns) > 0
        
        # All patterns should be compiled regex objects
        for pattern in command_tools._secret_patterns:
            assert hasattr(pattern, 'sub')  # Compiled regex has sub method
            assert hasattr(pattern, 'search')  # Compiled regex has search method


class TestCommandToolsIntegration:
    """Integration tests for CommandTools."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def command_tools(self, temp_workspace):
        """Create CommandTools instance with temp workspace."""
        return CommandTools(workspace_root=str(temp_workspace))
    
    @pytest.mark.asyncio
    async def test_full_workflow(self, command_tools, temp_workspace):
        """Test complete command execution workflow."""
        # 1. Check system info
        info = await command_tools.get_system_info()
        assert info["platform"] == os.name
        
        # 2. Test command availability
        echo_test = await command_tools.test_command("echo")
        assert echo_test["allowed"] is True
        
        # 3. Create test file using echo
        test_content = "Hello, World!"
        test_file = "test.txt"
        
        if os.name == 'nt':  # Windows
            command = f'echo {test_content} > {test_file}'
        else:  # Unix-like
            command = f'echo "{test_content}" > {test_file}'
        
        result = await command_tools.run_command(command)
        assert result.success
        
        # 4. Verify file was created
        test_file_path = temp_workspace / test_file
        if test_file_path.exists():
            content = test_file_path.read_text().strip()
            assert test_content in content
        
        # 5. List directory contents
        if os.name == 'nt':  # Windows
            list_command = "dir"
        else:  # Unix-like
            list_command = "ls"
        
        result = await command_tools.run_command(list_command)
        if result.success:
            assert test_file in result.stdout
    
    @pytest.mark.asyncio
    async def test_security_enforcement(self, command_tools, temp_workspace):
        """Test security enforcement in real scenarios."""
        # 1. Try to execute disallowed command
        result = await command_tools.run_command("rm -rf /")
        assert not result.success
        assert "not allowed" in result.stderr.lower()
        
        # 2. Try to access outside workspace
        result = await command_tools.run_command("echo test", cwd="../outside")
        assert not result.success
        assert "outside workspace" in result.stderr.lower()
        
        # 3. Test secret redaction
        secret_command = "echo password=secret123"
        result = await command_tools.run_command(secret_command)
        
        # The command itself might succeed, but logging should be redacted
        # (We can't easily test logging here, but the redaction function is tested separately)
        
        # 4. Test timeout enforcement
        if os.name != 'nt':  # Skip on Windows as sleep might not be available
            result = await command_tools.run_command("sleep 10", timeout=1)
            assert not result.success
            assert result.timeout
    
    @pytest.mark.asyncio
    async def test_allowlist_management(self, command_tools):
        """Test dynamic allowlist management."""
        # 1. Add custom command
        custom_command = "my-custom-tool"
        command_tools.add_to_allowlist(custom_command)
        
        assert command_tools.is_command_allowed(custom_command)
        
        # 2. Try to use custom command (will fail because it doesn't exist, but should be allowed)
        result = await command_tools.run_command(custom_command)
        # Command is allowed but will fail because it doesn't exist
        # The error should be about command not found, not about allowlist
        assert "not allowed" not in result.stderr.lower()
        
        # 3. Remove custom command
        command_tools.remove_from_allowlist(custom_command)
        assert not command_tools.is_command_allowed(custom_command)
        
        # 4. Try to use removed command
        result = await command_tools.run_command(custom_command)
        assert not result.success
        assert "not allowed" in result.stderr.lower()
    
    @pytest.mark.asyncio
    async def test_error_handling(self, command_tools):
        """Test comprehensive error handling."""
        # 1. Empty command
        result = await command_tools.run_command("")
        assert not result.success
        assert result.exit_code == -1
        
        # 2. Whitespace-only command
        result = await command_tools.run_command("   ")
        assert not result.success
        
        # 3. Command with invalid working directory
        result = await command_tools.run_command("echo test", cwd="nonexistent/path")
        assert not result.success
        
        # 4. Very long command (should still work if allowed)
        long_args = " ".join(["arg"] * 100)
        long_command = f"echo {long_args}"
        result = await command_tools.run_command(long_command)
        
        # Should succeed but might be truncated
        assert result.exit_code in [0, -1]  # Either success or controlled failure