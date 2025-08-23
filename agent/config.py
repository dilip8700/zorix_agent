"""Configuration management for Zorix Agent."""

import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Server configuration
    app_port: int = Field(default=8123, description="Application port")
    host: str = Field(default="127.0.0.1", description="Host to bind to")
    
    # Workspace configuration
    workspace_root: Path = Field(default=Path("./workspace"), description="Root directory for all operations")
    
    # AWS Bedrock configuration
    bedrock_region: str = Field(default="us-east-1", description="AWS Bedrock region")
    bedrock_model_id: str = Field(
        default="anthropic.claude-3-5-sonnet-20240620-v1:0",
        description="Bedrock model ID for reasoning"
    )
    bedrock_embed_model_id: str = Field(
        default="amazon.titan-embed-text-v2:0",
        description="Bedrock model ID for embeddings"
    )
    
    # LLM parameters
    max_tokens: int = Field(default=4000, description="Maximum tokens per request")
    temperature: float = Field(default=0.2, description="LLM temperature")
    request_timeout_secs: int = Field(default=120, description="Request timeout in seconds")
    
    # Observability
    otel_exporter_otlp_endpoint: Optional[str] = Field(
        default=None, 
        description="OpenTelemetry OTLP endpoint"
    )
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json or text)")
    log_file: Optional[str] = Field(default="logs/zorix-agent.log", description="Log file path")
    enable_tracing: bool = Field(default=False, description="Enable OpenTelemetry tracing")
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    audit_log_file: str = Field(default="logs/audit.log", description="Audit log file path")
    enable_audit_console: bool = Field(default=False, description="Enable audit logging to console")
    
    # Security
    command_allowlist: List[str] = Field(
        default=["npm", "yarn", "pnpm", "pytest", "python", "node", "go", "java", "mvn", "gradle", "make"],
        description="Allowed commands for execution"
    )
    command_timeout_secs: int = Field(default=90, description="Command execution timeout")
    
    # Vector and memory configuration
    vector_index_path: str = Field(default="data/vector_index", description="Vector index storage path")
    memory_db_path: str = Field(default="data/memory.db", description="Memory database path")
    embedding_model_id: str = Field(
        default="amazon.titan-embed-text-v2:0",
        description="Embedding model ID"
    )
    chunk_size: int = Field(default=1000, description="Text chunk size for indexing")
    chunk_overlap: int = Field(default=200, description="Overlap between text chunks")
    max_search_results: int = Field(default=10, description="Maximum search results to return")
    
    # Git configuration
    git_author_name: str = Field(default="Zorix Agent", description="Git author name")
    git_author_email: str = Field(default="zorix@local", description="Git author email")
    
    # Vector search
    vector_index_path: Path = Field(default=Path("./data/vector_index"), description="Vector index storage path")
    max_chunk_size: int = Field(default=1000, description="Maximum chunk size for code splitting")
    
    # Memory
    memory_db_path: Path = Field(default=Path("./data/memory.db"), description="SQLite database path")
    max_session_messages: int = Field(default=100, description="Maximum messages in session memory")
    
    @validator("workspace_root", "vector_index_path", "memory_db_path")
    def ensure_absolute_paths(cls, v):
        """Ensure paths are absolute."""
        return Path(v).resolve()
    
    @validator("workspace_root")
    def validate_workspace_root(cls, v):
        """Validate workspace root exists or can be created."""
        if not v.exists():
            try:
                v.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise ValueError(f"Cannot create workspace root {v}: {e}")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings


def validate_startup_config() -> None:
    """Validate configuration at startup and fail fast if invalid."""
    config = get_settings()
    
    # Ensure workspace root exists and is accessible
    if not config.workspace_root.exists():
        raise RuntimeError(f"Workspace root does not exist: {config.workspace_root}")
    
    if not config.workspace_root.is_dir():
        raise RuntimeError(f"Workspace root is not a directory: {config.workspace_root}")
    
    # Ensure data directories exist
    config.vector_index_path.parent.mkdir(parents=True, exist_ok=True)
    config.memory_db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Validate command allowlist is not empty
    if not config.command_allowlist:
        raise RuntimeError("Command allowlist cannot be empty")
    
    print(f"✓ Configuration validated")
    print(f"  Workspace: {config.workspace_root}")
    print(f"  Bedrock Region: {config.bedrock_region}")
    print(f"  Model: {config.bedrock_model_id}")
    print(f"  Port: {config.app_port}")