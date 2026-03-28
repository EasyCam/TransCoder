#!/bin/bash
# TransCoder PyPI Upload Script (Unix/Linux/macOS)
# Usage: ./upload_pypi.sh [--test]

set -e

echo "=================================="
echo "TransCoder PyPI Upload Script"
echo "=================================="

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

# Install build tools
echo "Installing build tools..."
python3 -m pip install --upgrade pip build twine

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info transcoder/*.egg-info

# Build the package
echo "Building package..."
python3 -m build

# Check the package
echo "Checking package..."
python3 -m twine check dist/*

# Upload to PyPI
if [ "$1" == "--test" ]; then
    echo "Uploading to Test PyPI..."
    python3 -m twine upload --repository testpypi dist/*
    echo ""
    echo "Package uploaded to Test PyPI!"
    echo "Install with: pip install --index-url https://test.pypi.org/simple/ transcoder-llm"
else
    echo "Uploading to PyPI..."
    python3 -m twine upload dist/*
    echo ""
    echo "Package uploaded to PyPI!"
    echo "Install with: pip install transcoder-llm"
fi

echo ""
echo "=================================="
echo "Upload completed successfully!"
echo "=================================="