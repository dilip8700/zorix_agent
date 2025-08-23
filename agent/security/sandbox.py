"""Security sandbox for safe file and command operations."""

import os
import re
import shlex
from pathlib import Path
from typing import List, Optional, Set

from agent.security.exceptions import SecurityError


class SecuritySandbox:
    """Security sandbox that enforces workspace confinement and validates operations."""
    
    def __init__(self, workspace_root: Path, denylist: Optional[List[str]] = None):
        """Initialize security sandbox.
        
        Args:
            workspace_root: Root directory for all operations
            denylist: List of path patterns to deny access to
        """
        self.workspace_root = workspace_root.resolve()
        self.denylist_patterns = denylist or self._get_default_denylist()
        
        # Compile regex patterns for efficiency
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.denylist_patterns
        ]
        
        # Ensure workspace root exists
        if not self.workspace_root.exists():
            raise SecurityError(f"Workspace root does not exist: {self.workspace_root}")
        
        if not self.workspace_root.is_dir():
            raise SecurityError(f"Workspace root is not a directory: {self.workspace_root}")
    
    def _get_default_denylist(self) -> List[str]:
        """Get default denylist patterns for sensitive paths."""
        return [
            # Sensitive files by name (within workspace)
            r"(^|[/\\])\.env$",
            r"(^|[/\\])\.env\..*$",
            r"(^|[/\\])password\.(txt|json|yaml|yml)$",
            r"(^|[/\\])secret\.(txt|json|yaml|yml|key)$",
            r"(^|[/\\])credentials\.(txt|json|yaml|yml)$",
            r"(^|[/\\])[^/\\]*\.key$",
            r"(^|[/\\])[^/\\]*\.pem$",
            r"(^|[/\\])[^/\\]*\.p12$",
            r"(^|[/\\])[^/\\]*\.pfx$",
            
            # Version control sensitive files
            r"(^|[/\\])\.git[/\\]config$",
            r"(^|[/\\])\.git[/\\]hooks[/\\].*",
            
            # SSH and certificates directories
            r"(^|[/\\])\.ssh[/\\].*",
            r"(^|[/\\])\.gnupg[/\\].*",
            r"(^|[/\\])\.aws[/\\]credentials$",
            
            # Database temporary files
            r".*\.db-wal$",
            r".*\.db-shm$",
        ]
    
    def validate_path(self, path: str) -> Path:
        """Validate and normalize a path for safe access.
        
        Args:
            path: Path to validate
            
        Returns:
            Normalized, validated Path object
            
        Raises:
            SecurityError: If path is invalid or outside workspace
        """
        if not path:
            raise SecurityError("Empty path provided")
        
        # Convert to Path and handle different path formats
        try:
            path_obj = Path(path)
        except Exception as e:
            raise SecurityError(f"Invalid path format: {path}") from e
        
        # If relative, make it relative to workspace root
        if not path_obj.is_absolute():
            path_obj = self.workspace_root / path_obj
        
        # Resolve to handle symlinks and .. references
        try:
            resolved_path = path_obj.resolve()
        except Exception as e:
            raise SecurityError(f"Cannot resolve path {path}: {e}") from e
        
        # Ensure path is within workspace boundaries
        try:
            resolved_path.relative_to(self.workspace_root)
        except ValueError:
            raise SecurityError(
                f"Path outside workspace: {resolved_path} not within {self.workspace_root}"
            )
        
        # Check against denylist patterns using relative path within workspace
        relative_path = str(resolved_path.relative_to(self.workspace_root))
        
        for i, pattern in enumerate(self._compiled_patterns):
            if pattern.search(relative_path):
                pattern_text = self.denylist_patterns[i]
                raise SecurityError(f"Path matches denylist pattern '{pattern_text}': {path}")
        
        return resolved_path
    
    def validate_paths(self, paths: List[str]) -> List[Path]:
        """Validate multiple paths.
        
        Args:
            paths: List of paths to validate
            
        Returns:
            List of validated Path objects
        """
        return [self.validate_path(path) for path in paths]
    
    def is_path_safe(self, path: str) -> bool:
        """Check if a path is safe without raising exceptions.
        
        Args:
            path: Path to check
            
        Returns:
            True if path is safe, False otherwise
        """
        try:
            self.validate_path(path)
            return True
        except SecurityError:
            return False
    
    def validate_command(self, command: str, allowlist: List[str]) -> bool:
        """Validate a command against an allowlist.
        
        Args:
            command: Command string to validate
            allowlist: List of allowed command names
            
        Returns:
            True if command is allowed
            
        Raises:
            SecurityError: If command is not allowed or contains dangerous patterns
        """
        if not command or not command.strip():
            raise SecurityError("Empty command provided")
        
        # Parse command to extract the binary name
        try:
            parsed = shlex.split(command.strip())
        except ValueError as e:
            raise SecurityError(f"Invalid command syntax: {command}") from e
        
        if not parsed:
            raise SecurityError("Empty command after parsing")
        
        binary = parsed[0]
        
        # Extract just the command name (handle paths)
        command_name = Path(binary).name
        
        # Check against allowlist
        if command_name not in allowlist:
            raise SecurityError(
                f"Command '{command_name}' not in allowlist. Allowed: {', '.join(allowlist)}"
            )
        
        # Check for dangerous patterns before parsing
        dangerous_patterns = [
            (r"&&", "command chaining with &&"),
            (r"\|\|", "command chaining with ||"),
            (r";\s*\w", "command separator ;"),  # Semicolon followed by word
            (r"\|[^|]", "pipe operator"),  # Single pipe (not ||)
            (r">[^>]", "output redirection"),  # Single > (not >>)
            (r"<", "input redirection"),
            (r"`", "command substitution with backticks"),
            (r"\$\(", "command substitution with $()"),
            (r"\brm\s+-rf\b", "dangerous rm -rf"),
            (r"\bsudo\b", "privilege escalation with sudo"),
            (r"\bsu\s", "privilege escalation with su"),
            (r"\bchmod\s+[0-7]{3,4}\b", "permission changes"),
            (r"\bchown\b", "ownership changes"),
            (r"curl.*\|.*sh", "dangerous curl pipe to shell"),
            (r"wget.*\|.*sh", "dangerous wget pipe to shell"),
        ]
        
        for pattern, description in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                raise SecurityError(f"Command contains dangerous pattern ({description}): {command}")
        
        return True
    
    def get_safe_working_directory(self, requested_cwd: Optional[str] = None) -> Path:
        """Get a safe working directory within the workspace.
        
        Args:
            requested_cwd: Requested working directory (relative to workspace)
            
        Returns:
            Safe working directory path
        """
        if requested_cwd is None:
            return self.workspace_root
        
        # Validate the requested directory
        safe_cwd = self.validate_path(requested_cwd)
        
        # Ensure it's a directory (or can be created)
        if safe_cwd.exists() and not safe_cwd.is_dir():
            raise SecurityError(f"Working directory is not a directory: {safe_cwd}")
        
        return safe_cwd
    
    def sanitize_output(self, output: str) -> str:
        """Sanitize command output by redacting potential secrets.
        
        Args:
            output: Raw output to sanitize
            
        Returns:
            Sanitized output with secrets redacted
        """
        if not output:
            return output
        
        # Patterns for potential secrets
        secret_patterns = [
            (r"password[=:\s]+[^\s\n]+", "password=***REDACTED***"),
            (r"token[=:\s]+[^\s\n]+", "token=***REDACTED***"),
            (r"key[=:\s]+[^\s\n]+", "key=***REDACTED***"),
            (r"secret[=:\s]+[^\s\n]+", "secret=***REDACTED***"),
            (r"api[_-]?key[=:\s]+[^\s\n]+", "api_key=***REDACTED***"),
            (r"access[_-]?token[=:\s]+[^\s\n]+", "access_token=***REDACTED***"),
            (r"bearer\s+[^\s\n]+", "bearer ***REDACTED***"),
            (r"authorization:\s*[^\s\n]+", "authorization: ***REDACTED***"),
            # AWS credentials
            (r"AKIA[0-9A-Z]{16}", "***REDACTED_AWS_ACCESS_KEY***"),
            (r"aws_access_key_id[=:\s]+[^\s\n]+", "aws_access_key_id=***REDACTED***"),
            (r"aws_secret_access_key[=:\s]+[^\s\n]+", "aws_secret_access_key=***REDACTED***"),
            # Generic base64-like patterns (be conservative)
            (r"[A-Za-z0-9+/]{40,}={0,2}", "***REDACTED_POTENTIAL_SECRET***"),
        ]
        
        sanitized = output
        for pattern, replacement in secret_patterns:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        
        return sanitized
    
    def check_file_permissions(self, path: Path) -> dict:
        """Check file permissions and ownership.
        
        Args:
            path: Path to check
            
        Returns:
            Dictionary with permission information
        """
        if not path.exists():
            return {"exists": False}
        
        stat = path.stat()
        
        return {
            "exists": True,
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
            "is_symlink": path.is_symlink(),
            "readable": os.access(path, os.R_OK),
            "writable": os.access(path, os.W_OK),
            "executable": os.access(path, os.X_OK),
            "size": stat.st_size,
            "mode": oct(stat.st_mode),
        }
    
    def get_workspace_stats(self) -> dict:
        """Get workspace statistics for monitoring.
        
        Returns:
            Dictionary with workspace statistics
        """
        total_files = 0
        total_size = 0
        file_types = {}
        
        try:
            for item in self.workspace_root.rglob("*"):
                if item.is_file():
                    total_files += 1
                    total_size += item.stat().st_size
                    
                    suffix = item.suffix.lower()
                    file_types[suffix] = file_types.get(suffix, 0) + 1
        except Exception:
            # Don't fail on permission errors
            pass
        
        return {
            "workspace_root": str(self.workspace_root),
            "total_files": total_files,
            "total_size_bytes": total_size,
            "file_types": file_types,
            "denylist_patterns": len(self.denylist_patterns),
        }