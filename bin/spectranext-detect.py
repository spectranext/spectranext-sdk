#!/usr/bin/env python3
"""
Spectranext USB CDC Device Detection
Finds USB CDC devices matching Spectranext vendor/product IDs and outputs environment variables.
"""

import sys
import argparse
import serial.tools.list_ports

# USB vendor/product IDs for spectranext
VENDOR_ID = 0x1337
PRODUCT_ID = 0x0001


def find_spectranext_devices():
    """
    Find all Spectranext USB CDC devices.
    
    Returns:
        Tuple of (list of device paths sorted by interface number, serial number)
    """
    ports = serial.tools.list_ports.comports()
    
    # Find spectranext devices
    spectranext_ports = []
    serial_number = None
    for port in ports:
        if port.vid == VENDOR_ID and port.pid == PRODUCT_ID:
            spectranext_ports.append(port.device)
            # Get serial number from first matching port (all interfaces share same serial)
            if serial_number is None:
                serial_number = port.serial_number
    
    # Sort ports - typically interfaces are in order (0, 1, etc.)
    spectranext_ports.sort()
    
    return spectranext_ports, serial_number


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
    
    # Device 0 = CLI/Console
    # Device 1 = USBFS
    # Device 2 = GDB Stub
    cli_port = devices[0] if len(devices) > 0 else None
    usbfs_port = devices[1] if len(devices) > 1 else None
    gdb_stub_port = devices[2] if len(devices) > 2 else None
    
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

