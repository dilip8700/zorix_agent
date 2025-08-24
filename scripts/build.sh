#!/bin/bash
# Build script for Zorix Agent

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
    echo -e "${BLUE}[BUILD]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Build version and metadata
VERSION=${VERSION:-"1.0.0"}
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

print_status "Building Zorix Agent v$VERSION"
print_status "Build date: $BUILD_DATE"
print_status "Git commit: $GIT_COMMIT"

# Function to build Docker image
build_docker_image() {
    local tag=${1:-"zorix-agent:$VERSION"}
    
    print_status "Building Docker image: $tag"
    
    docker build \
        -f infra/docker/agent.Dockerfile \
        --build-arg VERSION="$VERSION" \
        --build-arg BUILD_DATE="$BUILD_DATE" \
        --build-arg GIT_COMMIT="$GIT_COMMIT" \
        -t "$tag" \
        -t "zorix-agent:latest" \
        .
    
    print_success "Docker image built: $tag"
}

# Function to build Python package
build_python_package() {
    print_status "Building Python package..."
    
    # Clean previous builds
    rm -rf dist/ build/ *.egg-info/
    
    # Build wheel and source distribution
    python setup.py sdist bdist_wheel
    
    print_success "Python package built in dist/"
}

# Function to run pre-build checks
run_prebuild_checks() {
    print_status "Running pre-build checks..."
    
    # Check if Docker is available
    if ! command -v docker >/dev/null 2>&1; then
        print_error "Docker is required for building"
        exit 1
    fi
    
    # Check if git is available
    if ! command -v git >/dev/null 2>&1; then
        print_error "Git is required for version info"
        exit 1
    fi
    
    # Verify required files exist
    local required_files=(
        "requirements.txt"
        "main.py"
        "infra/docker/agent.Dockerfile"
    )
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            print_error "Required file missing: $file"
            exit 1
        fi
    done
    
    print_success "Pre-build checks passed"
}

# Function to create deployment artifacts
create_deployment_artifacts() {
    print_status "Creating deployment artifacts..."
    
    # Create deployment directory
    mkdir -p deployment/
    
    # Copy essential files
    cp compose.yaml deployment/
    cp .env.example deployment/
    cp -r scripts/ deployment/
    cp -r infra/ deployment/
    
    # Create deployment README
    cat > deployment/README.md << EOF
# Zorix Agent Deployment

Version: $VERSION
Build Date: $BUILD_DATE
Git Commit: $GIT_COMMIT

## Quick Start

1. Copy .env.example to .env and configure:
   \`\`\`bash
   cp .env.example .env
   # Edit .env with your AWS credentials and settings
   \`\`\`

2. Start with Docker Compose:
   \`\`\`bash
   docker-compose up -d
   \`\`\`

3. Check health:
   \`\`\`bash
   curl http://localhost:8000/health
   \`\`\`

## Configuration

See .env.example for all available configuration options.

## Monitoring

- Health check: http://localhost:8000/health
- API docs: http://localhost:8000/docs
- Metrics: http://localhost:8888/metrics (if observability profile enabled)

EOF
    
    print_success "Deployment artifacts created in deployment/"
}

# Function to test the built image
test_built_image() {
    local image=${1:-"zorix-agent:latest"}
    
    print_status "Testing built image: $image"
    
    # Start container in background
    local container_id=$(docker run -d -p 8001:8000 --name zorix-test "$image")
    
    # Wait for startup
    sleep 10
    
    # Test health endpoint
    if curl -f http://localhost:8001/health >/dev/null 2>&1; then
        print_success "Health check passed"
    else
        print_error "Health check failed"
        docker logs "$container_id"
        docker rm -f "$container_id"
        exit 1
    fi
    
    # Clean up
    docker rm -f "$container_id"
    
    print_success "Image test passed"
}

# Function to show help
show_help() {
    echo "Zorix Agent Build Script"
    echo
    echo "Usage: $0 [command]"
    echo
    echo "Commands:"
    echo "  docker         Build Docker image"
    echo "  package        Build Python package"  
    echo "  artifacts      Create deployment artifacts"
    echo "  test           Test built Docker image"
    echo "  all            Run all build steps"
    echo "  help           Show this help message"
    echo
    echo "Environment Variables:"
    echo "  VERSION        Version tag (default: 1.0.0)"
    echo "  TAG            Docker tag (default: zorix-agent:\$VERSION)"
    echo
}

# Main script logic
case "${1:-all}" in
    docker)
        run_prebuild_checks
        build_docker_image "${TAG:-zorix-agent:$VERSION}"
        ;;
    package)
        build_python_package
        ;;
    artifacts)
        create_deployment_artifacts
        ;;
    test)
        test_built_image "${TAG:-zorix-agent:latest}"
        ;;
    all)
        run_prebuild_checks
        build_docker_image "${TAG:-zorix-agent:$VERSION}"
        create_deployment_artifacts
        test_built_image "${TAG:-zorix-agent:$VERSION}"
        print_success "Build completed successfully!"
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