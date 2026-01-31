#!/usr/bin/env python3
"""
Spectranext USB CDC Device Detection
Finds USB CDC devices matching Spectranext vendor/product IDs and outputs environment variables.
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


def find_spectranext_devices():
    """
    Find all Spectranext USB CDC devices.
    
    Returns:
        Tuple of (dict mapping port types to device paths, serial number)
        Port types: 'cli', 'usbfs', 'gdb'
    """
    ports = serial.tools.list_ports.comports()
    
    # Find spectranext devices
    spectranext_ports = []
    serial_number = None
    for port in ports:
        if port.vid == VENDOR_ID and port.pid == PRODUCT_ID:
            spectranext_ports.append(port)
            # Get serial number from first matching port (all interfaces share same serial)
            if serial_number is None:
                serial_number = port.serial_number
    
    if len(spectranext_ports) == 0:
        return {}, None
    
    # On Windows, identify ports by description/name
    # On Mac/Linux, use order (device 0 = CLI, device 1 = USBFS, device 2 = GDB)
    result = {}
    
    if sys.platform == "win32":
        # Windows: identify ports by CDC interface number from hardware ID
        # USB CDC devices expose multiple interfaces, each gets a COM port
        # Interface 0 = CLI, Interface 1 = USBFS, Interface 2 = GDB
        import re
        
        for port in spectranext_ports:
            interface_num = None
            
            # Parse interface number from hwid string
            # pyserial format: USB VID:PID=1337:0001 SER=... LOCATION=1-6:x.2
            # The interface number is after the dot in LOCATION (e.g., x.2 = interface 2)
            # If no LOCATION field at all, it's interface 0 (CLI)
            hwid = getattr(port, 'hwid', '') or ''
            if hwid:
                # Try LOCATION format first (pyserial's format)
                match = re.search(r'LOCATION=[^ ]*\.(\d+)', hwid)
                if match:
                    interface_num = int(match.group(1))
                elif 'LOCATION=' in hwid:
                    # LOCATION exists but has no interface number (just "x" without .N) = interface 0 (CLI)
                    interface_num = 0
                else:
                    # No LOCATION field at all = interface 0 (CLI)
                    interface_num = 0
            else:
                # No hwid at all = interface 0 (CLI)
                interface_num = 0
            
            if interface_num is not None:
                # Based on Web Serial API: COM28=USBFS (interface 2), COM29=GDB (interface 4), COM30=CLI (no LOCATION/interface 0)
                if interface_num == 2:
                    result['usbfs'] = port.device
                elif interface_num == 4:
                    result['gdb'] = port.device
                elif interface_num == 0:
                    result['cli'] = port.device
        
        # If not found by interface number, fall back to order (shouldn't happen with proper detection)
        if 'cli' not in result and len(spectranext_ports) > 0:
            result['cli'] = spectranext_ports[0].device
        if 'usbfs' not in result and len(spectranext_ports) > 1:
            result['usbfs'] = spectranext_ports[1].device
        if 'gdb' not in result and len(spectranext_ports) > 2:
            result['gdb'] = spectranext_ports[2].device
    else:
        # Mac/Linux: use order
        if len(spectranext_ports) > 0:
            result['cli'] = spectranext_ports[0].device
        if len(spectranext_ports) > 1:
            result['usbfs'] = spectranext_ports[1].device
        if len(spectranext_ports) > 2:
            result['gdb'] = spectranext_ports[2].device
    
    return result, serial_number


def main():
    """Main function to detect devices and output environment variables"""
    parser = argparse.ArgumentParser(description='Spectranext USB CDC Device Detection')
    parser.add_argument('--cli', action='store_true', help='Output only CLI port')
    parser.add_argument('--usbfs', action='store_true', help='Output only USBFS port')
    parser.add_argument('--gdb', action='store_true', help='Output only GDB stub port')
    parser.add_argument('--serial', action='store_true', help='Output only serial number')
    args = parser.parse_args()
    
    devices, serial_number = find_spectranext_devices()
    
    if len(devices) == 0:
        print("Error: No Spectranext devices found", file=sys.stderr)
        sys.exit(1)
    
    cli_port = devices.get('cli')
    usbfs_port = devices.get('usbfs')
    gdb_stub_port = devices.get('gdb')
    
    if cli_port is None:
        print("Error: Could not find CLI port", file=sys.stderr)
        sys.exit(1)
    
    # Output based on flags
    if args.cli:
        print(cli_port)
    elif args.usbfs:
        if usbfs_port:
            print(usbfs_port)
        else:
            print("Error: Could not find USBFS port", file=sys.stderr)
            sys.exit(1)
    elif args.gdb:
        if gdb_stub_port:
            print(gdb_stub_port)
        else:
            print("Error: Could not find GDB stub port", file=sys.stderr)
            sys.exit(1)
    elif args.serial:
        if serial_number:
            print(serial_number)
        else:
            print("Error: Could not read serial number", file=sys.stderr)
            sys.exit(1)
    else:
        # Default: output environment variables in format suitable for sourcing
        print(f"SPECTRANEXT_CLI={cli_port}")
        if usbfs_port:
            print(f"SPECTRANEXT_USBFS={usbfs_port}")
        if gdb_stub_port:
            print(f"SPECTRANEXT_GDB_STUB={gdb_stub_port}")
        if serial_number:
            print(f"SPECTRANEXT_SERIAL={serial_number}")


if __name__ == '__main__':
    main()

