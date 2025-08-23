"""Exceptions for LLM operations."""


class LLMError(Exception):
    """Base exception for LLM operations."""
    pass


class BedrockError(LLMError):
    """Base exception for AWS Bedrock operations."""
    pass


class BedrockRateLimitError(BedrockError):
    """Exception for Bedrock rate limit exceeded."""
    pass


class BedrockTimeoutError(BedrockError):
    """Exception for Bedrock request timeout."""
    pass


class BedrockAuthError(BedrockError):
    """Exception for Bedrock authentication/authorization errors."""
    pass


class BedrockModelError(BedrockError):
    """Exception for Bedrock model-specific errors."""
    pass


class BedrockValidationError(BedrockError):
    """Exception for Bedrock request validation errors."""
    pass