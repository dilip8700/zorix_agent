"""Security-related exceptions for Zorix Agent."""


class SecurityError(Exception):
    """Base exception for security violations."""
    
    def __init__(self, message: str, details: dict = None):
        """Initialize security error.
        
        Args:
            message: Error message
            details: Additional error details
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class PathTraversalError(SecurityError):
    """Exception for path traversal attempts."""
    pass


class CommandNotAllowedError(SecurityError):
    """Exception for disallowed command execution attempts."""
    pass


class WorkspaceViolationError(SecurityError):
    """Exception for operations outside workspace boundaries."""
    pass


class DenylistViolationError(SecurityError):
    """Exception for accessing denylisted paths or patterns."""
    pass