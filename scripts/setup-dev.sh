#!/bin/bash

# Zorix Agent Development Environment Setup Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check if Python 3.11+ is available
check_python() {
    log_step "Checking Python version..."
    
    if command -v python3.11 &> /dev/null; then
        PYTHON_CMD="python3.11"
    elif command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        if [[ $(echo "$PYTHON_VERSION >= 3.11" | bc -l) -eq 1 ]]; then
            PYTHON_CMD="python3"
        else
            log_error "Python 3.11+ is required, found $PYTHON_VERSION"
            exit 1
        fi
    elif command -v python &> /dev/null; then
        PYTHON_VERSION=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        if [[ $(echo "$PYTHON_VERSION >= 3.11" | bc -l) -eq 1 ]]; then
            PYTHON_CMD="python"
        else
            log_error "Python 3.11+ is required, found $PYTHON_VERSION"
            exit 1
        fi
    else
        log_error "Python is not installed"
        exit 1
    fi
    
    log_info "Using Python: $PYTHON_CMD ($(${PYTHON_CMD} --version))"
}

# Create virtual environment
create_venv() {
    log_step "Creating virtual environment..."
    
    if [ -d "venv" ]; then
        log_warn "Virtual environment already exists"
        read -p "Remove existing venv and create new one? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf venv
        else
            log_info "Using existing virtual environment"
            return
        fi
    fi
    
    $PYTHON_CMD -m venv venv
    log_info "Virtual environment created"
}

# Activate virtual environment and install dependencies
install_dependencies() {
    log_step "Installing dependencies..."
    
    # Activate virtual environment
    source venv/bin/activate 2>/dev/null || source venv/Scripts/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install dependencies
    pip install -r requirements.txt
    
    # Install development dependencies if they exist
    if [ -f "requirements-dev.txt" ]; then
        pip install -r requirements-dev.txt
    fi
    
    log_info "Dependencies installed"
}

# Setup environment configuration
setup_env() {
    log_step "Setting up environment configuration..."
    
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_info "Created .env file from .env.example"
            log_warn "Please edit .env file with your AWS credentials and configuration"
        else
            log_warn "No .env.example file found, creating basic .env file"
            cat > .env << EOF
# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
ZORIX_BEDROCK_REGION=us-east-1

# Application Configuration
ZORIX_WORKSPACE_ROOT=./workspace
ZORIX_LOG_LEVEL=DEBUG
ZORIX_LOG_FORMAT=text

# Database Configuration
ZORIX_MEMORY_DB_PATH=./data/memory.db
ZORIX_VECTOR_INDEX_PATH=./data/vector_index

# Web Configuration
ZORIX_WEB_HOST=127.0.0.1
ZORIX_WEB_PORT=8000
EOF
            log_warn "Please edit .env file with your actual configuration"
        fi
    else
        log_info ".env file already exists"
    fi
}

# Create necessary directories
create_directories() {
    log_step "Creating necessary directories..."
    
    mkdir -p data logs workspace
    
    # Create .gitkeep files to ensure directories are tracked
    touch data/.gitkeep logs/.gitkeep workspace/.gitkeep
    
    log_info "Directories created"
}

# Initialize database
init_database() {
    log_step "Initializing database..."
    
    # Activate virtual environment
    source venv/bin/activate 2>/dev/null || source venv/Scripts/activate
    
    # Check if init script exists
    if [ -f "scripts/init-db.sql" ]; then
        # Create database directory if it doesn't exist
        mkdir -p "$(dirname "$(grep ZORIX_MEMORY_DB_PATH .env | cut -d'=' -f2 | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')")"
        
        log_info "Database initialization script found"
        # Note: SQLite databases are created automatically when first accessed
    fi
    
    log_info "Database initialization completed"
}

# Run basic tests
run_tests() {
    log_step "Running basic tests..."
    
    # Activate virtual environment
    source venv/bin/activate 2>/dev/null || source venv/Scripts/activate
    
    # Check if pytest is available
    if command -v pytest &> /dev/null; then
        # Run a basic test to ensure everything is working
        if [ -f "test_basic.py" ]; then
            python test_basic.py
            log_info "Basic tests passed"
        else
            log_warn "No basic test file found, skipping tests"
        fi
    else
        log_warn "pytest not available, skipping tests"
    fi
}

# Check AWS configuration
check_aws_config() {
    log_step "Checking AWS configuration..."
    
    # Activate virtual environment
    source venv/bin/activate 2>/dev/null || source venv/Scripts/activate
    
    # Load environment variables
    if [ -f ".env" ]; then
        export $(grep -v '^#' .env | xargs)
    fi
    
    # Check if AWS credentials are set
    if [ -z "$AWS_ACCESS_KEY_ID" ] || [ "$AWS_ACCESS_KEY_ID" = "your_access_key_here" ]; then
        log_warn "AWS credentials not configured in .env file"
        log_warn "Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
        return
    fi
    
    # Test AWS connection
    python -c "
import boto3
import os
try:
    client = boto3.client('bedrock', region_name=os.getenv('ZORIX_BEDROCK_REGION', 'us-east-1'))
    models = client.list_foundation_models()
    print('AWS Bedrock connection successful')
except Exception as e:
    print(f'AWS Bedrock connection failed: {e}')
" 2>/dev/null || log_warn "Could not verify AWS Bedrock connection"
}

# Show next steps
show_next_steps() {
    log_info "Development environment setup completed!"
    echo
    echo -e "${BLUE}Next steps:${NC}"
    echo "1. Edit .env file with your AWS credentials and configuration"
    echo "2. Activate the virtual environment:"
    echo "   source venv/bin/activate  # On Linux/Mac"
    echo "   venv\\Scripts\\activate     # On Windows"
    echo "3. Start the development server:"
    echo "   python run_web.py"
    echo "4. Or use the CLI:"
    echo "   python zorix_cli.py --help"
    echo
    echo -e "${BLUE}Useful commands:${NC}"
    echo "  python zorix_cli.py status          # Check system status"
    echo "  python zorix_cli.py chat \"hello\"     # Test chat interface"
    echo "  python run_web.py                   # Start web server"
    echo
    echo -e "${BLUE}Web Interface:${NC}"
    echo "  http://localhost:8000/static/index.html"
    echo "  http://localhost:8000/docs (API documentation)"
    echo
    if [ -f ".env" ] && grep -q "your_access_key_here" .env; then
        echo -e "${YELLOW}⚠️  Don't forget to update your AWS credentials in .env file!${NC}"
    fi
}

# Main setup function
main() {
    log_info "Starting Zorix Agent development environment setup..."
    echo
    
    check_python
    create_venv
    install_dependencies
    setup_env
    create_directories
    init_database
    run_tests
    check_aws_config
    
    echo
    show_next_steps
}

# Handle command line arguments
case "${1:-setup}" in
    "setup")
        main
        ;;
    "clean")
        log_info "Cleaning development environment..."
        rm -rf venv data logs __pycache__ .pytest_cache
        find . -name "*.pyc" -delete
        find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
        log_info "Environment cleaned"
        ;;
    "test")
        log_info "Running tests..."
        source venv/bin/activate 2>/dev/null || source venv/Scripts/activate
        if command -v pytest &> /dev/null; then
            pytest tests/ -v
        else
            python -m unittest discover tests/
        fi
        ;;
    "help")
        echo "Usage: $0 [setup|clean|test|help]"
        echo
        echo "Commands:"
        echo "  setup  - Set up development environment (default)"
        echo "  clean  - Clean up generated files and virtual environment"
        echo "  test   - Run test suite"
        echo "  help   - Show this help message"
        ;;
    *)
        log_error "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac