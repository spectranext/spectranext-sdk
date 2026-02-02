#!/usr/bin/env python3
"""
Spectranext USB CDC Device Detection
Finds USB CDC devices matching Spectranext vendor/product IDs and outputs environment variables.
Now detects a single unified CDC interface.
"""

import sys
import os

# Check if pyserial is available, and if not, try to use venv Python
try:
    import serial.tools.list_ports
except ImportError:
    # pyserial not found - try to find and use venv Python
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sdk_dir = os.path.dirname(script_dir)
    
    # Check for venv Python
    if sys.platform == "win32":
        venv_python_path = os.path.join(sdk_dir, "venv", "Scripts", "python.exe")
    else:
        venv_python_path = os.path.join(sdk_dir, "venv", "bin", "python3")
    
    if os.path.exists(venv_python_path):
        # Re-execute with venv Python
        import subprocess
        sys.exit(subprocess.call([venv_python_path] + sys.argv))
    else:
        # No venv found - give helpful error
        print("Error: pyserial module not found.", file=sys.stderr)
        print("Please install dependencies:", file=sys.stderr)
        print(f"  python -m pip install -r {os.path.join(sdk_dir, 'requirements.txt')}", file=sys.stderr)
        print("Or use the SDK's venv Python if available.", file=sys.stderr)
        sys.exit(1)

import argparse
import serial.tools.list_ports

# USB vendor/product IDs for spectranext
VENDOR_ID = 0x1337
PRODUCT_ID = 0x0001


def find_spectranext_device():
    """
    Find the Spectranext USB CDC device (single unified interface).
    
    Returns:
        Tuple of (port device path, serial number) or (None, None) if not found
    """
    ports = serial.tools.list_ports.comports()
    
    # Find first spectranext device
    for port in ports:
        if port.vid == VENDOR_ID and port.pid == PRODUCT_ID:
            return port.device, port.serial_number
    
    return None, None


def main():
    """Main function to detect device and output environment variables"""
    parser = argparse.ArgumentParser(description='Spectranext USB CDC Device Detection')
    parser.add_argument('--cli', action='store_true', help='Output only CLI port')
    parser.add_argument('--serial', action='store_true', help='Output only serial number')
    args = parser.parse_args()
    
    port, serial_number = find_spectranext_device()
    
    if port is None:
        print("Error: No Spectranext devices found", file=sys.stderr)
        sys.exit(1)
    
    # Output based on flags
    if args.cli:
        print(port)
    elif args.serial:
        if serial_number:
            print(serial_number)
        else:
            print("Error: Could not read serial number", file=sys.stderr)
            sys.exit(1)
    else:
        # Default: output environment variables in format suitable for sourcing
        print(f"SPECTRANEXT_CLI={port}")
        if serial_number:
            print(f"SPECTRANEXT_SERIAL={serial_number}")


if __name__ == '__main__':
    main()
