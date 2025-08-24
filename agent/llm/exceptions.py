"""Exceptions for LLM operations."""


class LLMError(Exception):
    """Base exception for LLM operations."""
    pass


class BedrockError(Exception):
    """Base exception for Bedrock operations."""
    pass


class BedrockRateLimitError(BedrockError):
    """Exception for rate limit exceeded."""
    pass


class BedrockTimeoutError(BedrockError):
    """Exception for timeout errors."""
    pass


class BedrockServiceError(BedrockError):
    """Exception for Bedrock service errors."""
    pass


class BedrockValidationError(BedrockError):
    """Exception for validation errors."""
    pass


class BedrockAccessDeniedError(BedrockError):
    """Exception for access denied errors."""
    pass