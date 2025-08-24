#!/bin/bash
# Development script for Zorix Agent

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to setup Python environment
setup_python_env() {
    print_status "Setting up Python environment..."
    
    # Check Python version
    if ! command_exists python3; then
        print_error "Python 3.11+ is required"
        exit 1
    fi
    
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if [[ $(echo "$python_version < 3.11" | bc -l) -eq 1 ]]; then
        print_error "Python 3.11+ is required, found $python_version"
        exit 1
    fi
    
    # Create virtual environment if it doesn't exist
    if [[ ! -d "venv" ]]; then
        print_status "Creating virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    print_status "Activating virtual environment..."
    source venv/bin/activate
    
    # Upgrade pip
    print_status "Upgrading pip..."
    pip install --upgrade pip
    
    # Install dependencies
    print_status "Installing dependencies..."
    pip install -r requirements.txt
    
    print_success "Python environment setup complete"
}

# Function to setup development tools
setup_dev_tools() {
    print_status "Setting up development tools..."
    
    # Install development dependencies
    if [[ -f "requirements-dev.txt" ]]; then
        pip install -r requirements-dev.txt
    fi
    
    # Install pre-commit hooks if available
    if command_exists pre-commit && [[ -f ".pre-commit-config.yaml" ]]; then
        print_status "Installing pre-commit hooks..."
        pre-commit install
    fi
    
    print_success "Development tools setup complete"
}

# Function to run linting
run_linting() {
    print_status "Running linting..."
    
    # Run ruff for linting
    if command_exists ruff; then
        print_status "Running ruff linting..."
        ruff check . --fix
    else
        print_warning "ruff not found, skipping linting"
    fi
    
    # Run black for formatting
    if command_exists black; then
        print_status "Running black formatting..."
        black . --check --diff
    else
        print_warning "black not found, skipping formatting"
    fi
    
    # Run mypy for type checking
    if command_exists mypy; then
        print_status "Running mypy type checking..."
        mypy agent/ --ignore-missing-imports
    else
        print_warning "mypy not found, skipping type checking"
    fi
    
    print_success "Linting complete"
}

# Function to run tests
run_tests() {
    print_status "Running tests..."
    
    if command_exists pytest; then
        # Run tests with coverage
        pytest tests/ -v --cov=agent --cov-report=html --cov-report=term
        print_success "Tests completed successfully"
    else
        print_warning "pytest not found, skipping tests"
    fi
}

# Function to start development server
start_dev_server() {
    print_status "Starting development server..."
    
    # Check if .env file exists
    if [[ ! -f ".env" ]]; then
        if [[ -f ".env.example" ]]; then
            print_warning ".env file not found, copying from .env.example"
            cp .env.example .env
            print_warning "Please edit .env file with your AWS credentials"
        else
            print_error ".env file not found and no .env.example available"
            exit 1
        fi
    fi
    
    # Start the server
    print_status "Starting Zorix Agent on http://127.0.0.1:8000"
    python main.py
}

# Function to rebuild vector index
rebuild_index() {
    print_status "Rebuilding vector index..."
    
    # Create workspace directory if it doesn't exist
    mkdir -p workspace
    
    # Call the index rebuild endpoint
    if command_exists curl; then
        curl -X POST http://127.0.0.1:8000/index/rebuild \
             -H "Content-Type: application/json" \
             -d '{}' || print_warning "Failed to rebuild index (server may not be running)"
    else
        print_warning "curl not found, cannot rebuild index automatically"
    fi
}

# Function to clean up
cleanup() {
    print_status "Cleaning up..."
    
    # Remove Python cache files
    find . -type f -name "*.pyc" -delete
    find . -type d -name "__pycache__" -delete
    
    # Remove test artifacts
    rm -rf .pytest_cache/
    rm -rf htmlcov/
    rm -rf .coverage
    
    # Remove mypy cache
    rm -rf .mypy_cache/
    
    print_success "Cleanup complete"
}

# Function to build Docker image
build_docker() {
    print_status "Building Docker image..."
    
    docker build -f infra/docker/agent.Dockerfile -t zorix-agent:latest .
    
    print_success "Docker image built successfully"
}

# Function to run with Docker Compose
run_docker_compose() {
    print_status "Starting with Docker Compose..."
    
    # Check if .env file exists
    if [[ ! -f ".env" ]]; then
        print_error ".env file required for Docker Compose"
        exit 1
    fi
    
    docker-compose up --build
}

# Function to show help
show_help() {
    echo "Zorix Agent Development Script"
    echo
    echo "Usage: $0 [command]"
    echo
    echo "Commands:"
    echo "  setup          Setup development environment"
    echo "  lint           Run linting and formatting"
    echo "  test           Run test suite"
    echo "  server         Start development server"
    echo "  index          Rebuild vector index"
    echo "  clean          Clean up generated files"
    echo "  docker         Build Docker image"
    echo "  compose        Run with Docker Compose"
    echo "  all            Run setup, lint, test"
    echo "  help           Show this help message"
    echo
}

# Main script logic
case "${1:-help}" in
    setup)
        setup_python_env
        setup_dev_tools
        ;;
    lint)
        run_linting
        ;;
    test)
        run_tests
        ;;
    server)
        start_dev_server
        ;;
    index)
        rebuild_index
        ;;
    clean)
        cleanup
        ;;
    docker)
        build_docker
        ;;
    compose)
        run_docker_compose
        ;;
    all)
        setup_python_env
        setup_dev_tools
        run_linting
        run_tests
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac