# Multi-stage Dockerfile for Zorix Agent
# Stage 1: Build stage
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create and set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt pyproject.toml ./

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy source code
COPY . .

# Install the package in development mode
RUN pip install -e .

# Stage 2: Production stage
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    ZORIX_ENV=production

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd -r zorix && useradd -r -g zorix zorix

# Create application directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=zorix:zorix . .

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/workspace && \
    chown -R zorix:zorix /app

# Switch to non-root user
USER zorix

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/system/health || exit 1

# Default command
CMD ["python", "run_web.py"]

# Stage 3: Development stage
FROM builder as development

# Install development dependencies
RUN pip install pytest pytest-asyncio pytest-cov black ruff mypy

# Set development environment
ENV ZORIX_ENV=development

# Create directories
RUN mkdir -p /app/data /app/logs /app/workspace

# Expose port and debugger port
EXPOSE 8000 5678

# Default command for development
CMD ["python", "run_web.py"]