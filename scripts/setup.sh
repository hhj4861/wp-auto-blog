#!/bin/bash
# Setup script for wp-auto-blog

set -e

echo "==================================="
echo "wp-auto-blog Setup"
echo "==================================="

# Navigate to project directory
cd "$(dirname "$0")/.."

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
python -m pip install -r requirements.txt

# Copy .env.example if .env doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "Please edit .env with your API keys"
fi

# Create data directories
echo "Creating data directories..."
mkdir -p data/cache data/logs data/coverage

echo ""
echo "==================================="
echo "Setup complete!"
echo "==================================="
echo ""
echo "Next steps:"
echo "1. Edit .env with your API keys"
echo "2. Run tests: ./scripts/test.sh"
echo "3. Run pipeline: python -m src.main --dry-run"
