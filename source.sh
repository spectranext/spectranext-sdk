#!/bin/bash

# Get the directory where this script is located
# Works in both bash and zsh when sourced
if [ -n "${BASH_SOURCE[0]}" ]; then
    # Bash - BASH_SOURCE[0] works when sourced
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
elif [ -n "$ZSH_VERSION" ]; then
    # Zsh - ${(%):-%x} expands to the file being sourced
    # Must be used at top level, not in a function
    zsh_script_file="${(%):-%x}"
    if [ -n "$zsh_script_file" ] && [ -f "$zsh_script_file" ]; then
        SCRIPT_DIR="$(cd "$(dirname "$zsh_script_file")" && pwd)"
    fi
    unset zsh_script_file
fi

# Verify the directory exists and contains source.sh
if [ -z "$SCRIPT_DIR" ] || [ ! -f "$SCRIPT_DIR/source.sh" ]; then
    return 1 2>/dev/null || exit 1
fi

# Add to PATH
export PATH="$SCRIPT_DIR/bin:$SCRIPT_DIR/z88dk/bin:$PATH"

# Set ZCCCFG environment variable
# Try to detect the actual location, fallback to standard path
ZCCCFG_PATH="$SCRIPT_DIR/z88dk/share/z88dk/lib/config"
if [ ! -d "$ZCCCFG_PATH" ]; then
    # Try alternative locations
    if [ -d "$SCRIPT_DIR/z88dk/lib/config" ]; then
        ZCCCFG_PATH="$SCRIPT_DIR/z88dk/lib/config"
    elif [ -d "$SCRIPT_DIR/z88dk/config" ]; then
        ZCCCFG_PATH="$SCRIPT_DIR/z88dk/config"
    else
        # Fallback to standard path
        ZCCCFG_PATH="$SCRIPT_DIR/z88dk/share/z88dk/lib/config"
    fi
fi
export ZCCCFG="$ZCCCFG_PATH"

# Export CMake toolchain configuration for z88dk
export ZCCTARGET="zx"
if [ -f "$SCRIPT_DIR/z88dk/support/cmake/Toolchain-zcc.cmake" ]; then
    export SPECTRANEXT_TOOLCHAIN="$SCRIPT_DIR/z88dk/support/cmake/Toolchain-zcc.cmake"
fi

# Export SDK include directory
export SPECTRANEXT_INCLUDE_DIR="$SCRIPT_DIR/include"

# Export CMake SDK path
export SPECTRANEXT_SDK_PATH="$SCRIPT_DIR"

# Source SPX helper script
if [ -f "$SCRIPT_DIR/bin/spx.sh" ]; then
    source "$SCRIPT_DIR/bin/spx.sh"
fi

