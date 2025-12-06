#!/bin/bash
# SPX helper script - provides binutils-style commands for SPX
# Usage: source sdk/bin/spx.sh

_SPX_PORT=""
_SPX_SCRIPT_DIR=""

# Find script directory
if [ -n "${BASH_SOURCE[0]}" ]; then
    _SPX_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
elif [ -n "$0" ]; then
    _SPX_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
else
    # Fallback: assume we're in the SDK bin directory
    _SPX_SCRIPT_DIR="$(pwd)/bin"
fi

# Get Python command (must be defined first)
# Prefers venv Python from SDK, falls back to system Python
_spx_get_python() {
    local python_cmd=""
    
    # First, try venv Python from SDK directory
    if [ -n "$SPX_SDK_DIR" ] && [ -d "$SPX_SDK_DIR/venv" ]; then
        if [ -x "$SPX_SDK_DIR/venv/bin/python3" ]; then
            python_cmd="$SPX_SDK_DIR/venv/bin/python3"
            if "$python_cmd" --version >/dev/null 2>&1; then
                echo "$python_cmd"
                return 0
            fi
        elif [ -x "$SPX_SDK_DIR/venv/bin/python" ]; then
            python_cmd="$SPX_SDK_DIR/venv/bin/python"
            if "$python_cmd" --version >/dev/null 2>&1; then
                echo "$python_cmd"
                return 0
            fi
        fi
    fi
    
    # Fallback to system Python
    # Try python3 first
    if command -v python3 >/dev/null 2>&1; then
        python_cmd=$(command -v python3)
        # Verify it actually works
        if [ -n "$python_cmd" ] && "$python_cmd" --version >/dev/null 2>&1; then
            echo "$python_cmd"
            return 0
        fi
    fi
    
    # Try python
    if command -v python >/dev/null 2>&1; then
        python_cmd=$(command -v python)
        # Verify it actually works
        if [ -n "$python_cmd" ] && "$python_cmd" --version >/dev/null 2>&1; then
            echo "$python_cmd"
            return 0
        fi
    fi
    
    # Try common locations (use full paths)
    for py_cmd in python3 python; do
        for prefix in "$HOME/.pyenv/versions/" "/usr/local/bin/" "/opt/homebrew/bin/" "/usr/bin/"; do
            local full_path="${prefix}${py_cmd}"
            if [ -x "$full_path" ]; then
                if "$full_path" --version >/dev/null 2>&1; then
                    echo "$full_path"
                    return 0
                fi
            fi
        done
    done
    
    echo "Error: Python not found" >&2
    return 1
}

# Find port by interface number (0 = console, 1 = USBFS)
_spx_find_port_by_interface() {
    local interface=$1
    local python_cmd
    python_cmd=$(_spx_get_python)
    if [ $? -ne 0 ]; then
        return 1
    fi
    
    local port=$("$python_cmd" -c "
import serial.tools.list_ports
ports = [p.device for p in serial.tools.list_ports.comports() 
         if p.vid == 0x1337 and p.pid == 0x0001]
ports.sort()
if len(ports) > $interface:
    print(ports[$interface])
elif len(ports) == 1 and $interface == 0:
    print(ports[0])
else:
    print('')
" 2>/dev/null)
    
    if [ -n "$port" ]; then
        echo "$port"
        return 0
    fi
    return 1
}

_spx_find_port() {
    # Find USBFS port (interface 1)
    _SPX_PORT=$(_spx_find_port_by_interface 1)
    [ -n "$_SPX_PORT" ]
}

_spx_find_console_port() {
    # Find console port (interface 0)
    _spx_find_port_by_interface 0
}

# Initialize port on first use
_spx_get_port() {
    if [ -z "$_SPX_PORT" ]; then
        _spx_find_port
    fi
    
    if [ -z "$_SPX_PORT" ]; then
        echo "Error: Could not find SPX device" >&2
        return 1
    fi
    
    echo "$_SPX_PORT"
}

# Set port manually if needed
spx-set-port() {
    _SPX_PORT="$1"
    echo "SPX port set to: $_SPX_PORT"
}

# List directory
spx-ls() {
    local port=$(_spx_get_port)
    [ $? -ne 0 ] && return 1
    
    local python_cmd=$(_spx_get_python)
    [ $? -ne 0 ] && return 1
    
    local path="${1:-/}"
    "$python_cmd" "$_SPX_SCRIPT_DIR/spx.py" --port "$port" ls "$path"
}

# Download file
spx-get() {
    local port=$(_spx_get_port)
    [ $? -ne 0 ] && return 1
    
    local python_cmd=$(_spx_get_python)
    [ $? -ne 0 ] && return 1
    
    if [ $# -lt 2 ]; then
        echo "Usage: spx-get <remote> <local>" >&2
        return 1
    fi
    
    "$python_cmd" "$_SPX_SCRIPT_DIR/spx.py" --port "$port" get "$1" "$2"
}

# Upload file
spx-put() {
    local port=$(_spx_get_port)
    [ $? -ne 0 ] && return 1
    
    local python_cmd=$(_spx_get_python)
    [ $? -ne 0 ] && return 1
    
    if [ $# -lt 2 ]; then
        echo "Usage: spx-put <local> <remote>" >&2
        return 1
    fi
    
    "$python_cmd" "$_SPX_SCRIPT_DIR/spx.py" --port "$port" put "$1" "$2"
}

# Copy (alias for put)
spx-cp() {
    spx-put "$@"
}

# Move/rename
spx-mv() {
    local port=$(_spx_get_port)
    [ $? -ne 0 ] && return 1
    
    local python_cmd=$(_spx_get_python)
    [ $? -ne 0 ] && return 1
    
    if [ $# -lt 2 ]; then
        echo "Usage: spx-mv <old> <new>" >&2
        return 1
    fi
    
    "$python_cmd" "$_SPX_SCRIPT_DIR/spx.py" --port "$port" mv "$1" "$2"
}

# Delete file
spx-rm() {
    local port=$(_spx_get_port)
    [ $? -ne 0 ] && return 1
    
    local python_cmd=$(_spx_get_python)
    [ $? -ne 0 ] && return 1
    
    if [ $# -lt 1 ]; then
        echo "Usage: spx-rm <path>" >&2
        return 1
    fi
    
    "$python_cmd" "$_SPX_SCRIPT_DIR/spx.py" --port "$port" rm "$1"
}

# Create directory
spx-mkdir() {
    local port=$(_spx_get_port)
    [ $? -ne 0 ] && return 1
    
    local python_cmd=$(_spx_get_python)
    [ $? -ne 0 ] && return 1
    
    if [ $# -lt 1 ]; then
        echo "Usage: spx-mkdir <path>" >&2
        return 1
    fi
    
    "$python_cmd" "$_SPX_SCRIPT_DIR/spx.py" --port "$port" mkdir "$1"
}

# Remove directory
spx-rmdir() {
    local port=$(_spx_get_port)
    [ $? -ne 0 ] && return 1
    
    local python_cmd=$(_spx_get_python)
    [ $? -ne 0 ] && return 1
    
    if [ $# -lt 1 ]; then
        echo "Usage: spx-rmdir <path>" >&2
        return 1
    fi
    
    "$python_cmd" "$_SPX_SCRIPT_DIR/spx.py" --port "$port" rmdir "$1"
}

# Reboot ZX Spectrum
spx-reboot() {
    local port=$(_spx_get_port)
    [ $? -ne 0 ] && return 1
    
    local python_cmd=$(_spx_get_python)
    [ $? -ne 0 ] && return 1
    
    "$python_cmd" "$_SPX_SCRIPT_DIR/spx.py" --port "$port" reboot
}

# Configure autoboot from xfs://ram/ and reboot ZX Spectrum
spx-autoboot() {
    local port=$(_spx_get_port)
    [ $? -ne 0 ] && return 1
    
    local python_cmd=$(_spx_get_python)
    [ $? -ne 0 ] && return 1
    
    "$python_cmd" "$_SPX_SCRIPT_DIR/spx.py" --port "$port" autoboot
}

# Launch minicom terminal on console port
spx-terminal() {
    local console_port=$(_spx_find_console_port)
    if [ -z "$console_port" ]; then
        echo "Error: Could not find SPX console port" >&2
        return 1
    fi
    
    if ! command -v minicom >/dev/null 2>&1; then
        echo "Error: minicom not found. Please install minicom:" >&2
        echo "  macOS: brew install minicom" >&2
        echo "  Linux: sudo apt-get install minicom" >&2
        return 1
    fi
    
    echo "Launching minicom on $console_port (115200 baud)"
    minicom -D "$console_port" -b 115200
}

# Print usage
spx-help() {
    cat <<EOF
SPX Commands:
  spx-ls [path]          List directory (default: /)
  spx-get <remote> <local>  Download file
  spx-put <local> <remote>  Upload file
  spx-cp <local> <remote>   Alias for spx-put
  spx-mv <old> <new>     Move/rename file
  spx-rm <path>          Delete file
  spx-mkdir <path>       Create directory
  spx-rmdir <path>       Remove directory
  spx-reboot             Trigger ZX Spectrum reboot
  spx-autoboot           Configure autoboot from xfs://ram/ and reboot ZX Spectrum
  spx-terminal           Launch minicom terminal on console port
EOF
}

