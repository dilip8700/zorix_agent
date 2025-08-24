"""Configuration management for Zorix Agent."""

import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    def __init__(self, **kwargs):
        # Import from CENTRAL_CONFIG.py for all settings
        try:
            from CENTRAL_CONFIG import (
                SERVER_PORT, SERVER_HOST, BEDROCK_REGION, BEDROCK_MODEL_ID, 
                BEDROCK_EMBED_MODEL_ID, MAX_TOKENS, TEMPERATURE, REQUEST_TIMEOUT_SECONDS,
                WORKSPACE_ROOT, DATA_DIR, LOGS_DIR, VECTOR_INDEX_PATH, MEMORY_DB_PATH,
                ALLOWED_COMMANDS, COMMAND_TIMEOUT_SECONDS, LOG_LEVEL, LOG_FORMAT,
                GIT_AUTHOR_NAME, GIT_AUTHOR_EMAIL, MAX_CHUNK_SIZE, MAX_SESSION_MESSAGES
            )
            
            # Apply central config if not overridden
            if 'app_port' not in kwargs:
                kwargs['app_port'] = SERVER_PORT
            if 'host' not in kwargs:
                kwargs['host'] = SERVER_HOST
            if 'bedrock_region' not in kwargs:
                kwargs['bedrock_region'] = BEDROCK_REGION
            if 'bedrock_model_id' not in kwargs:
                kwargs['bedrock_model_id'] = BEDROCK_MODEL_ID
            if 'bedrock_embed_model_id' not in kwargs:
                kwargs['bedrock_embed_model_id'] = BEDROCK_EMBED_MODEL_ID
            if 'max_tokens' not in kwargs:
                kwargs['max_tokens'] = MAX_TOKENS
            if 'temperature' not in kwargs:
                kwargs['temperature'] = TEMPERATURE
            if 'request_timeout_secs' not in kwargs:
                kwargs['request_timeout_secs'] = REQUEST_TIMEOUT_SECONDS
            if 'workspace_root' not in kwargs:
                kwargs['workspace_root'] = Path(WORKSPACE_ROOT)
            if 'vector_index_path' not in kwargs:
                kwargs['vector_index_path'] = Path(VECTOR_INDEX_PATH)
            if 'memory_db_path' not in kwargs:
                kwargs['memory_db_path'] = Path(MEMORY_DB_PATH)
            if 'command_allowlist' not in kwargs:
                kwargs['command_allowlist'] = ",".join(ALLOWED_COMMANDS)
            if 'command_timeout_secs' not in kwargs:
                kwargs['command_timeout_secs'] = COMMAND_TIMEOUT_SECONDS
            if 'log_level' not in kwargs:
                kwargs['log_level'] = LOG_LEVEL
            if 'log_format' not in kwargs:
                kwargs['log_format'] = LOG_FORMAT
            if 'git_author_name' not in kwargs:
                kwargs['git_author_name'] = GIT_AUTHOR_NAME
            if 'git_author_email' not in kwargs:
                kwargs['git_author_email'] = GIT_AUTHOR_EMAIL
            if 'max_chunk_size' not in kwargs:
                kwargs['max_chunk_size'] = MAX_CHUNK_SIZE
            if 'max_session_messages' not in kwargs:
                kwargs['max_session_messages'] = MAX_SESSION_MESSAGES
                
        except ImportError:
            pass  # Use defaults if CENTRAL_CONFIG not available
        
        super().__init__(**kwargs)
    
    # Server configuration - CENTRALIZED IN CENTRAL_CONFIG.py
    app_port: int = Field(default=8001, description="Application port - Change in CENTRAL_CONFIG.py")
    host: str = Field(default="127.0.0.1", description="Host to bind to - Change in CENTRAL_CONFIG.py")
    
    # Workspace configuration
    workspace_root: Path = Field(default=Path("./workspace"), description="Root directory for all operations")
    
    # AWS configuration
    aws_access_key_id: Optional[str] = Field(default=None, description="AWS Access Key ID")
    aws_secret_access_key: Optional[str] = Field(default=None, description="AWS Secret Access Key")
    aws_session_token: Optional[str] = Field(default=None, description="AWS Session Token")
    aws_region: Optional[str] = Field(default=None, description="AWS Default Region")
    
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
    command_allowlist: str = Field(
        default="npm,yarn,pnpm,pytest,python,node,go,java,mvn,gradle,make",
        description="Comma-separated list of allowed commands for execution"
    )
    command_timeout_secs: int = Field(default=90, description="Command execution timeout")
    
    # Git configuration
    git_author_name: str = Field(default="Zorix Agent", description="Git author name")
    git_author_email: str = Field(default="zorix@local", description="Git author email")
    
    # Vector search
    vector_index_path: Path = Field(default=Path("./data/vector_index"), description="Vector index storage path")
    max_chunk_size: int = Field(default=1000, description="Maximum chunk size for code splitting")
    
    # Memory
    memory_db_path: Path = Field(default=Path("./data/memory.db"), description="SQLite database path")
    max_session_messages: int = Field(default=100, description="Maximum messages in session memory")
    
    @property
    def command_allowlist_parsed(self) -> List[str]:
        """Parse command allowlist from string to list."""
        return [cmd.strip() for cmd in self.command_allowlist.split(",") if cmd.strip()]
    
    @field_validator("workspace_root", "vector_index_path", "memory_db_path")
    @classmethod
    def ensure_absolute_paths(cls, v):
        """Ensure paths are absolute."""
        return Path(v).resolve()
    
    @field_validator("workspace_root")
    @classmethod
    def validate_workspace_root(cls, v):
        """Validate workspace root exists or can be created."""
        path = Path(v) if not isinstance(v, Path) else v
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise ValueError(f"Cannot create workspace root {path}: {e}")
        return path
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields instead of raising errors


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