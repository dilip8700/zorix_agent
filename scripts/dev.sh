#!/bin/bash
# Development server startup script

set -e

echo "🚀 Starting Zorix Agent development server..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your AWS credentials and configuration"
fi

# Create workspace directory
mkdir -p workspace
mkdir -p data

# Validate configuration
echo "✅ Validating configuration..."
python -c "from agent.config import validate_startup_config; validate_startup_config()"

# Start development server
echo "🌟 Starting FastAPI development server..."
uvicorn agent.api:app --host 127.0.0.1 --port 8123 --reload