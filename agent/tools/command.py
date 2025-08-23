"""Command execution tools with allowlist enforcement and security."""

import asyncio
import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agent.config import get_settings
from agent.security.sandbox import SecuritySandbox
from agent.security.exceptions import SecurityError
from agent.models.base import CommandResult

logger = logging.getLogger(__name__)


class CommandTools:
    """Command execution with allowlist enforcement and security sandbox."""
    
    # Default allowlist of safe commands
    DEFAULT_ALLOWLIST = [
        # Build tools
        "npm", "yarn", "pnpm", "node",
        "pip", "python", "python3", "poetry", "pipenv",
        "cargo", "rustc",
        "go", "gofmt", "golint",
        "mvn", "gradle", "javac", "java",
        "make", "cmake", "ninja",
        "dotnet", "msbuild",
        
        # Testing tools
        "pytest", "jest", "mocha", "phpunit", "rspec",
        "cargo test", "go test", "mvn test",
        
        # Linting and formatting
        "eslint", "prettier", "black", "flake8", "mypy",
        "clippy", "rustfmt", "gofmt",
        
        # Version control (basic)
        "git", "git status", "git diff", "git log", "git show",
        "git add", "git commit", "git push", "git pull",
        "git branch", "git checkout", "git merge", "git --version",
        
        # File operations (safe)
        "ls", "dir", "cat", "type", "head", "tail",
        "find", "grep", "wc", "sort", "uniq",
        
        # System info (safe)
        "pwd", "cd", "whoami", "date", "echo",
        "which", "where", "env", "timeout", "sleep",
        "powershell", "cmd",
    ]
    
    # Patterns for secret redaction
    SECRET_PATTERNS = [
        r'(?i)(password|passwd|pwd)[=:\s]+[^\s]+',
        r'(?i)(token|key|secret)[=:\s]+[^\s]+',
        r'(?i)(api[_-]?key)[=:\s]+[^\s]+',
        r'(?i)(auth[_-]?token)[=:\s]+[^\s]+',
        r'(?i)(bearer\s+)[^\s]+',
        r'(?i)(basic\s+)[^\s]+',
        r'[A-Za-z0-9+/]{20,}={0,2}',  # Base64-like strings
        r'[0-9a-fA-F]{32,}',  # Hex strings (potential keys)
    ]
    
    def __init__(
        self,
        workspace_root: Optional[str] = None,
        allowlist: Optional[List[str]] = None,
        max_output_size: int = 1024 * 1024,  # 1MB
        default_timeout: int = 300  # 5 minutes
    ):
        """Initialize command tools.
        
        Args:
            workspace_root: Root directory for command execution
            allowlist: List of allowed commands. If None, uses default.
            max_output_size: Maximum size of command output in bytes
            default_timeout: Default timeout for commands in seconds
        """
        settings = get_settings()
        self.workspace_root = Path(workspace_root or settings.workspace_root).resolve()
        self.sandbox = SecuritySandbox(self.workspace_root)
        
        # Set up allowlist
        self.allowlist = allowlist or self.DEFAULT_ALLOWLIST.copy()
        
        # Add any configured allowlist from settings
        if hasattr(settings, 'command_allowlist') and settings.command_allowlist:
            self.allowlist.extend(settings.command_allowlist)
        
        self.max_output_size = max_output_size
        self.default_timeout = default_timeout
        
        # Compile secret patterns for efficiency
        self._secret_patterns = [re.compile(pattern) for pattern in self.SECRET_PATTERNS]
        
        # Ensure workspace exists
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized CommandTools with workspace: {self.workspace_root}")
        logger.info(f"Allowlist contains {len(self.allowlist)} commands")
    
    def is_command_allowed(self, command: str) -> bool:
        """Check if a command is in the allowlist.
        
        Args:
            command: Command to check
            
        Returns:
            True if command is allowed, False otherwise
        """
        command = command.strip()
        
        # Check exact matches first
        if command in self.allowlist:
            return True
        
        # Check if command starts with any allowlisted command
        for allowed in self.allowlist:
            if command.startswith(allowed + " ") or command == allowed:
                return True
        
        # Check base command (first word)
        base_command = command.split()[0] if command.split() else ""
        if base_command in self.allowlist:
            return True
        
        return False
    
    async def run_command(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
        env: Optional[Dict[str, str]] = None,
        capture_output: bool = True,
        shell: bool = True
    ) -> CommandResult:
        """Execute a command with security checks and output limits.
        
        Args:
            command: Command to execute
            cwd: Working directory (relative to workspace root)
            timeout: Timeout in seconds (uses default if None)
            env: Environment variables to add/override
            capture_output: Whether to capture stdout/stderr
            shell: Whether to run command through shell
            
        Returns:
            CommandResult with execution details
            
        Raises:
            SecurityError: If command is not allowed or path is invalid
            ValueError: If command is invalid
        """
        start_time = time.time()
        
        try:
            # Validate command
            if not command or not command.strip():
                raise ValueError("Command cannot be empty")
            
            command = command.strip()
            
            # Check allowlist
            if not self.is_command_allowed(command):
                raise SecurityError(f"Command not allowed: {command}")
            
            # Validate and resolve working directory
            if cwd:
                abs_cwd = self.sandbox.validate_path(cwd)
                if not abs_cwd.is_dir():
                    raise ValueError(f"Working directory does not exist: {cwd}")
            else:
                abs_cwd = self.workspace_root
            
            # Set up environment
            exec_env = os.environ.copy()
            if env:
                exec_env.update(env)
            
            # Set timeout
            exec_timeout = timeout or self.default_timeout
            
            logger.info(f"Executing command: {self._redact_secrets(command)}")
            logger.debug(f"Working directory: {abs_cwd}")
            logger.debug(f"Timeout: {exec_timeout}s")
            
            # Execute command
            if capture_output:
                process = await asyncio.create_subprocess_shell(
                    command,
                    cwd=abs_cwd,
                    env=exec_env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    shell=shell
                )
                
                try:
                    stdout_data, stderr_data = await asyncio.wait_for(
                        process.communicate(),
                        timeout=exec_timeout
                    )
                    
                    # Decode output
                    stdout = stdout_data.decode('utf-8', errors='replace') if stdout_data else ""
                    stderr = stderr_data.decode('utf-8', errors='replace') if stderr_data else ""
                    
                    # Limit output size
                    if len(stdout) > self.max_output_size:
                        stdout = stdout[:self.max_output_size] + "\n[OUTPUT TRUNCATED]"
                    
                    if len(stderr) > self.max_output_size:
                        stderr = stderr[:self.max_output_size] + "\n[OUTPUT TRUNCATED]"
                    
                except asyncio.TimeoutError:
                    # Kill the process if it times out
                    process.kill()
                    await process.wait()
                    
                    duration = time.time() - start_time
                    
                    return CommandResult(
                        command=command,
                        exit_code=-1,
                        stdout="",
                        stderr=f"Command timed out after {exec_timeout} seconds",
                        duration=duration,
                        success=False,
                        working_directory=str(abs_cwd),
                        timeout=True
                    )
                
                exit_code = process.returncode
                
            else:
                # Run without capturing output
                process = await asyncio.create_subprocess_shell(
                    command,
                    cwd=abs_cwd,
                    env=exec_env,
                    shell=shell
                )
                
                try:
                    exit_code = await asyncio.wait_for(
                        process.wait(),
                        timeout=exec_timeout
                    )
                    stdout = ""
                    stderr = ""
                    
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    
                    duration = time.time() - start_time
                    
                    return CommandResult(
                        command=command,
                        exit_code=-1,
                        stdout="",
                        stderr=f"Command timed out after {exec_timeout} seconds",
                        duration=duration,
                        success=False,
                        working_directory=str(abs_cwd),
                        timeout=True
                    )
            
            duration = time.time() - start_time
            success = exit_code == 0
            
            # Create result
            result = CommandResult(
                command=command,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration=duration,
                success=success,
                working_directory=str(abs_cwd),
                timeout=False
            )
            
            # Log result (with secret redaction)
            if success:
                logger.info(f"Command completed successfully in {duration:.2f}s")
            else:
                logger.warning(f"Command failed with exit code {exit_code} in {duration:.2f}s")
            
            # Log output (redacted)
            if stdout:
                logger.debug(f"STDOUT: {self._redact_secrets(stdout[:500])}")
            if stderr:
                logger.debug(f"STDERR: {self._redact_secrets(stderr[:500])}")
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Command execution failed: {e}")
            
            return CommandResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration=duration,
                success=False,
                working_directory=str(abs_cwd) if 'abs_cwd' in locals() else str(self.workspace_root),
                timeout=False,
                error=str(e)
            )
    
    def _redact_secrets(self, text: str) -> str:
        """Redact potential secrets from text.
        
        Args:
            text: Text to redact
            
        Returns:
            Text with secrets redacted
        """
        if not text:
            return text
        
        redacted = text
        
        for pattern in self._secret_patterns:
            redacted = pattern.sub('[REDACTED]', redacted)
        
        return redacted
    
    def add_to_allowlist(self, commands: Union[str, List[str]]) -> None:
        """Add commands to the allowlist.
        
        Args:
            commands: Command or list of commands to add
        """
        if isinstance(commands, str):
            commands = [commands]
        
        for command in commands:
            if command not in self.allowlist:
                self.allowlist.append(command)
                logger.info(f"Added command to allowlist: {command}")
    
    def remove_from_allowlist(self, commands: Union[str, List[str]]) -> None:
        """Remove commands from the allowlist.
        
        Args:
            commands: Command or list of commands to remove
        """
        if isinstance(commands, str):
            commands = [commands]
        
        for command in commands:
            if command in self.allowlist:
                self.allowlist.remove(command)
                logger.info(f"Removed command from allowlist: {command}")
    
    def get_allowlist(self) -> List[str]:
        """Get current allowlist.
        
        Returns:
            Copy of current allowlist
        """
        return self.allowlist.copy()
    
    async def which(self, command: str) -> Optional[str]:
        """Find the path to a command.
        
        Args:
            command: Command to find
            
        Returns:
            Path to command if found, None otherwise
        """
        try:
            if os.name == 'nt':  # Windows
                result = await self.run_command(f"where {command}", capture_output=True)
            else:  # Unix-like
                result = await self.run_command(f"which {command}", capture_output=True)
            
            if result.success and result.stdout.strip():
                return result.stdout.strip().split('\n')[0]  # First result
            
            return None
            
        except Exception as e:
            logger.debug(f"Failed to find command {command}: {e}")
            return None
    
    async def test_command(self, command: str) -> Dict[str, Any]:
        """Test if a command is available and working.
        
        Args:
            command: Command to test
            
        Returns:
            Dictionary with test results
        """
        base_command = command.split()[0] if command.split() else command
        
        # Check if command is allowed
        allowed = self.is_command_allowed(command)
        
        # Try to find command path
        command_path = await self.which(base_command)
        
        # Try to run command with --version or --help
        version_result = None
        if allowed and command_path:
            try:
                # Try common version flags
                for flag in ['--version', '-v', '--help', '-h']:
                    try:
                        result = await self.run_command(
                            f"{base_command} {flag}",
                            timeout=10,
                            capture_output=True
                        )
                        if result.success:
                            version_result = result
                            break
                    except:
                        continue
            except Exception as e:
                logger.debug(f"Failed to test command {command}: {e}")
        
        return {
            "command": command,
            "base_command": base_command,
            "allowed": allowed,
            "available": command_path is not None,
            "path": command_path,
            "working": version_result is not None and version_result.success,
            "version_output": version_result.stdout[:200] if version_result else None
        }
    
    async def get_system_info(self) -> Dict[str, Any]:
        """Get system information using safe commands.
        
        Returns:
            Dictionary with system information
        """
        info = {
            "platform": os.name,
            "workspace_root": str(self.workspace_root),
            "allowlist_size": len(self.allowlist)
        }
        
        # Try to get additional info with safe commands
        safe_commands = {
            "pwd": "pwd" if os.name != 'nt' else "cd",
            "whoami": "whoami",
            "date": "date",
            "python_version": "python --version",
            "node_version": "node --version",
            "git_version": "git --version"
        }
        
        for key, cmd in safe_commands.items():
            try:
                if self.is_command_allowed(cmd):
                    result = await self.run_command(cmd, timeout=5, capture_output=True)
                    if result.success:
                        info[key] = result.stdout.strip()
            except Exception as e:
                logger.debug(f"Failed to get {key}: {e}")
                info[key] = None
        
        return info

