#!/usr/bin/env python3
"""
🎯 CENTRAL CONFIGURATION FOR ZORIX AGENT
=========================================

🚨 CHANGE ALL SETTINGS HERE - THEY WILL APPLY EVERYWHERE!

This is the SINGLE source of truth for ALL Zorix Agent configuration.
When you change values here, they automatically apply to:
- Web servers (all startup scripts)
- CLI tools
- API endpoints
- Model configurations
- AWS settings
- All documentation URLs

📝 HOW TO USE:
1. Change any value below
2. Restart any running servers
3. Everything will use the new settings automatically

🔧 CONFIGURATION SECTIONS:
- Server Settings (Port, Host)
- AI Model Settings (Bedrock Models)
- AWS Configuration
- System Limits
- Security Settings
"""

# ============================================================================
# 🌐 SERVER CONFIGURATION
# ============================================================================

# 🎯 MAIN SERVER PORT - Change this to change port everywhere
SERVER_PORT = 8002
SERVER_HOST = "127.0.0.1"

# Derived URLs (automatically generated)
BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
API_DOCS_URL = f"{BASE_URL}/docs"
HEALTH_URL = f"{BASE_URL}/health"
CHAT_URL = f"{BASE_URL}/static/index.html"

# ============================================================================
# 🤖 AI MODEL CONFIGURATION
# ============================================================================

# 🎯 BEDROCK MODELS - Change these to use different AI models
BEDROCK_REGION = "us-east-1"
BEDROCK_MODEL_ID = "anthropic.claude-3-5-sonnet-20240620-v1:0"
BEDROCK_EMBED_MODEL_ID = "amazon.titan-embed-text-v2:0"

# Alternative models you can switch to:
# BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"  # Faster, cheaper
# BEDROCK_MODEL_ID = "anthropic.claude-3-opus-20240229-v1:0"   # Most powerful
# BEDROCK_EMBED_MODEL_ID = "amazon.titan-embed-text-v1"        # Alternative embedding

# 🎯 AI PARAMETERS
MAX_TOKENS = 4000
TEMPERATURE = 0.2
REQUEST_TIMEOUT_SECONDS = 120

# ============================================================================
# ☁️ AWS CONFIGURATION
# ============================================================================

# 🎯 AWS CREDENTIALS (can be overridden by environment variables)
AWS_ACCESS_KEY_ID = None  # Set in .env file or environment
AWS_SECRET_ACCESS_KEY = None  # Set in .env file or environment
AWS_SESSION_TOKEN = None  # Optional
AWS_DEFAULT_REGION = "us-east-1"

# ============================================================================
# 📁 WORKSPACE CONFIGURATION
# ============================================================================

# 🎯 PATHS
WORKSPACE_ROOT = "./workspace"
DATA_DIR = "./data"
LOGS_DIR = "./logs"
VECTOR_INDEX_PATH = f"{DATA_DIR}/vector_index"
MEMORY_DB_PATH = f"{DATA_DIR}/memory.db"

# ============================================================================
# 🔒 SECURITY CONFIGURATION
# ============================================================================

# 🎯 ALLOWED COMMANDS - Add/remove commands as needed
ALLOWED_COMMANDS = [
    "npm", "yarn", "pnpm", "node", "npx",
    "python", "python3", "pip", "pip3", "pytest",
    "java", "javac", "mvn", "gradle",
    "go", "go run", "go build", "go test",
    "make", "cmake",
    "git", "curl", "wget",
    "ls", "dir", "cat", "type", "echo",
    "mkdir", "rmdir", "cp", "copy", "mv", "move"
]

COMMAND_TIMEOUT_SECONDS = 90

# ============================================================================
# 📊 SYSTEM LIMITS
# ============================================================================

# 🎯 PERFORMANCE SETTINGS
MAX_SEARCH_RESULTS = 20
MAX_CHUNK_SIZE = 1000
MAX_SESSION_MESSAGES = 100
POLL_INTERVAL_SECONDS = 2
REQUEST_TIMEOUT_SECONDS = 30

# ============================================================================
# 📝 LOGGING CONFIGURATION
# ============================================================================

# 🎯 LOGGING SETTINGS
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT = "json"  # json or text
LOG_FILE = f"{LOGS_DIR}/zorix-agent.log"
AUDIT_LOG_FILE = f"{LOGS_DIR}/audit.log"
ENABLE_CONSOLE_LOGS = True
ENABLE_AUDIT_LOGS = True

# ============================================================================
# 🔧 GIT CONFIGURATION
# ============================================================================

# 🎯 GIT SETTINGS
GIT_AUTHOR_NAME = "Zorix Agent"
GIT_AUTHOR_EMAIL = "zorix@local"

# ============================================================================
# 🎛️ FEATURE FLAGS
# ============================================================================

# 🎯 ENABLE/DISABLE FEATURES
ENABLE_TRACING = False
ENABLE_METRICS = True
ENABLE_VECTOR_SEARCH = True
ENABLE_MEMORY = True
ENABLE_GIT_OPERATIONS = True
ENABLE_COMMAND_EXECUTION = True

# ============================================================================
# 🚀 HELPER FUNCTIONS
# ============================================================================

def get_server_config():
    """Get server configuration."""
    return {
        "host": SERVER_HOST,
        "port": SERVER_PORT,
        "base_url": BASE_URL
    }

def get_model_config():
    """Get AI model configuration."""
    return {
        "region": BEDROCK_REGION,
        "model_id": BEDROCK_MODEL_ID,
        "embed_model_id": BEDROCK_EMBED_MODEL_ID,
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
        "timeout": REQUEST_TIMEOUT_SECONDS
    }

def get_aws_config():
    """Get AWS configuration."""
    return {
        "access_key_id": AWS_ACCESS_KEY_ID,
        "secret_access_key": AWS_SECRET_ACCESS_KEY,
        "session_token": AWS_SESSION_TOKEN,
        "region": AWS_DEFAULT_REGION,
        "bedrock_region": BEDROCK_REGION
    }

def get_security_config():
    """Get security configuration."""
    return {
        "allowed_commands": ALLOWED_COMMANDS,
        "command_timeout": COMMAND_TIMEOUT_SECONDS,
        "workspace_root": WORKSPACE_ROOT
    }

def get_paths_config():
    """Get paths configuration."""
    return {
        "workspace_root": WORKSPACE_ROOT,
        "data_dir": DATA_DIR,
        "logs_dir": LOGS_DIR,
        "vector_index_path": VECTOR_INDEX_PATH,
        "memory_db_path": MEMORY_DB_PATH
    }

def print_current_config():
    """Print current configuration summary."""
    print("🎯 ZORIX AGENT CENTRAL CONFIGURATION")
    print("=" * 50)
    print(f"🌐 Server: {BASE_URL}")
    print(f"🤖 AI Model: {BEDROCK_MODEL_ID}")
    print(f"☁️  AWS Region: {BEDROCK_REGION}")
    print(f"📁 Workspace: {WORKSPACE_ROOT}")
    print(f"🔒 Commands: {len(ALLOWED_COMMANDS)} allowed")
    print()
    print("🌐 Access URLs:")
    print(f"   • Main Interface: {BASE_URL}")
    print(f"   • Chat Interface: {CHAT_URL}")
    print(f"   • API Documentation: {API_DOCS_URL}")
    print(f"   • Health Check: {HEALTH_URL}")
    print()
    print("💡 To change settings: Edit CENTRAL_CONFIG.py")

def validate_config():
    """Validate configuration settings."""
    issues = []
    
    # Check port range
    if not (1024 <= SERVER_PORT <= 65535):
        issues.append(f"Invalid port {SERVER_PORT}. Use 1024-65535")
    
    # Check model ID format
    if not BEDROCK_MODEL_ID or ":" not in BEDROCK_MODEL_ID:
        issues.append(f"Invalid model ID: {BEDROCK_MODEL_ID}")
    
    # Check timeout values
    if REQUEST_TIMEOUT_SECONDS < 10:
        issues.append("Request timeout too low (minimum 10 seconds)")
    
    if issues:
        print("⚠️ Configuration Issues:")
        for issue in issues:
            print(f"   • {issue}")
        return False
    
    print("✅ Configuration validation passed")
    return True

# ============================================================================
# 🎯 EXPORT ALL SETTINGS
# ============================================================================

# Export for easy importing
__all__ = [
    # Server
    'SERVER_PORT', 'SERVER_HOST', 'BASE_URL', 'API_DOCS_URL', 'HEALTH_URL', 'CHAT_URL',
    # Models
    'BEDROCK_REGION', 'BEDROCK_MODEL_ID', 'BEDROCK_EMBED_MODEL_ID', 
    'MAX_TOKENS', 'TEMPERATURE', 'REQUEST_TIMEOUT_SECONDS',
    # AWS
    'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'AWS_DEFAULT_REGION',
    # Paths
    'WORKSPACE_ROOT', 'DATA_DIR', 'LOGS_DIR', 'VECTOR_INDEX_PATH', 'MEMORY_DB_PATH',
    # Security
    'ALLOWED_COMMANDS', 'COMMAND_TIMEOUT_SECONDS',
    # System
    'MAX_SEARCH_RESULTS', 'MAX_CHUNK_SIZE', 'MAX_SESSION_MESSAGES',
    # Functions
    'get_server_config', 'get_model_config', 'get_aws_config', 
    'get_security_config', 'get_paths_config', 'print_current_config', 'validate_config'
]

if __name__ == "__main__":
    print_current_config()
    validate_config()