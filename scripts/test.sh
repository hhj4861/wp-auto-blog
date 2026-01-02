#!/bin/bash
# Run tests for wp-auto-blog

set -e

echo "==================================="
echo "Running Tests"
echo "==================================="

# Navigate to project directory
cd "$(dirname "$0")/.."

# Activate virtual environment
source venv/bin/activate

# Run pytest with coverage
echo ""
echo "Running pytest with coverage..."
python -m pytest tests/ \
    -v \
    --tb=short \
    --cov=src \
    --cov-report=term-missing \
    --cov-report=html:data/coverage \
    --cov-fail-under=80 \
    "$@"

echo ""
echo "==================================="
echo "Tests complete!"
echo "==================================="
echo "Coverage report: data/coverage/index.html"
