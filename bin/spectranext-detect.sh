#!/bin/bash
# Spectranext USB CDC Device Detection
# Finds USB CDC devices matching Spectranext vendor/product IDs and outputs environment variables.

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Find SDK directory (parent of bin/)
SDK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Find Python from venv
PYTHON_EXECUTABLE=""
if [ -x "$SDK_DIR/venv/bin/python3" ]; then
    PYTHON_EXECUTABLE="$SDK_DIR/venv/bin/python3"
elif [ -x "$SDK_DIR/venv/bin/python" ]; then
    PYTHON_EXECUTABLE="$SDK_DIR/venv/bin/python"
else
    # Fallback to system Python
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_EXECUTABLE="$(command -v python3)"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_EXECUTABLE="$(command -v python)"
    else
        echo "Error: Python not found" >&2
        exit 1
    fi
fi

# Run the Python detection script
"$PYTHON_EXECUTABLE" "$SCRIPT_DIR/spectranext-detect.py" "$@"

