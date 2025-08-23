#!/bin/bash
# Production build script

set -e

echo "🏗️  Building Zorix Agent for production..."

# Run code quality checks
echo "🔍 Running code quality checks..."
black --check agent/ cli/ tests/
ruff check agent/ cli/ tests/
mypy agent/ cli/

# Run tests
echo "🧪 Running tests..."
pytest --cov=agent --cov-report=term-missing

# Build Docker image
echo "🐳 Building Docker image..."
docker build -f infra/docker/agent.Dockerfile -t zorix-agent:latest .

echo "✅ Build completed successfully!"
echo "🚀 Run with: docker run -p 8123:8123 --env-file .env zorix-agent:latest"