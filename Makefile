# Zorix Agent Makefile

.PHONY: help install dev test lint format clean build docker-build docker-run

help: ## Show this help message
	@echo "Zorix Agent - Development Commands"
	@echo "=================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install -r requirements.txt

dev: ## Start development server
	python main.py

test: ## Run tests
	python test_basic.py
	@echo "✅ Basic tests completed"

test-full: ## Run full test suite (when implemented)
	pytest tests/ -v

lint: ## Run linting
	ruff check agent/ cli/ tests/
	mypy agent/ cli/

format: ## Format code
	black agent/ cli/ tests/
	ruff check --fix agent/ cli/ tests/

clean: ## Clean up generated files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .coverage htmlcov/

build: ## Build for production
	@echo "🏗️  Building Zorix Agent..."
	$(MAKE) lint
	$(MAKE) test
	@echo "✅ Build completed"

docker-build: ## Build Docker image
	docker build -f infra/docker/agent.Dockerfile -t zorix-agent:latest .

docker-run: ## Run Docker container
	docker run -p 8123:8123 --env-file .env -v $(PWD)/workspace:/app/workspace zorix-agent:latest

setup: ## Initial setup
	@echo "🚀 Setting up Zorix Agent..."
	@if [ ! -f .env ]; then cp .env.example .env; echo "📝 Created .env file - please configure it"; fi
	@mkdir -p workspace data
	$(MAKE) install
	@echo "✅ Setup completed"

validate: ## Validate configuration
	python -c "from agent.config import validate_startup_config; validate_startup_config()"

index-rebuild: ## Rebuild vector index
	curl -X POST http://localhost:8123/index/rebuild

health: ## Check service health
	curl http://localhost:8123/healthz