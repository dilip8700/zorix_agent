# Multi-stage Docker build for Zorix Agent
FROM python:3.11-slim as builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    ripgrep \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd -r zorix && useradd -r -g zorix -d /app -s /bin/bash zorix

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /home/zorix/.local

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/workspace /app/data /app/logs \
    && chown -R zorix:zorix /app

# Switch to non-root user
USER zorix

# Add local bin to PATH
ENV PATH=/home/zorix/.local/bin:$PATH

# Set environment variables
ENV PYTHONPATH=/app
ENV WORKSPACE_ROOT=/app/workspace
ENV APP_PORT=8000
ENV BEDROCK_REGION=us-east-1
ENV BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20240620-v1:0
ENV BEDROCK_EMBED_MODEL_ID=amazon.titan-embed-text-v2:0
ENV MAX_TOKENS=4000
ENV TEMPERATURE=0.2
ENV REQUEST_TIMEOUT_SECS=120
ENV COMMAND_TIMEOUT_SECS=90
ENV GIT_AUTHOR_NAME="Zorix Agent"
ENV GIT_AUTHOR_EMAIL="zorix@local"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "main.py"]
