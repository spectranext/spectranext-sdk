#!/usr/bin/env python3
"""
SPX - Spectranext tool
Provides binutils-style commands for browsing and managing RAMFS over USB CDC.
"""

import sys
import serial
import serial.tools.list_ports
import argparse
import os
import time
from typing import Optional, Tuple

# USB vendor/product IDs for spectranext
VENDOR_ID = 0x1337
PRODUCT_ID = 0x0001

# CDC interface numbers (0 = console, 1 = USBFS)
USBFS_INTERFACE = 1


def find_spx_port_by_interface(interface: int = 1) -> Optional[str]:
    """
    Find SPX port by interface number.
    
    Args:
        interface: Interface number (0 = console, 1 = USBFS)
    
    Returns:
        Port device path or None if not found
    """
    ports = serial.tools.list_ports.comports()
    
    # Find spectranext device
    spectranext_ports = []
    for port in ports:
        if port.vid == VENDOR_ID and port.pid == PRODUCT_ID:
            spectranext_ports.append(port.device)
    
    # Sort ports - typically second interface comes after first
    spectranext_ports.sort()
    
    if len(spectranext_ports) > interface:
        return spectranext_ports[interface]
    elif len(spectranext_ports) == 1 and interface == 0:
        # Only one port found, assume it's console if looking for interface 0
        return spectranext_ports[0]
    
    return None


class USBFSException(Exception):
    """Base exception for USBFS errors"""
    pass


class USBFSNotFoundError(USBFSException):
    """File or directory not found"""
    pass


class USBFSPermissionError(USBFSException):
    """Permission denied"""
    pass


class USBFSExistsError(USBFSException):
    """File or directory already exists"""
    pass


class USBFSInvalidError(USBFSException):
    """Invalid command or parameter"""
    pass


class USBFSIOError(USBFSException):
    """I/O error"""
    pass


class SPXConnection:
    """Connection to SPX device"""
    
    def __init__(self, port: Optional[str] = None, show_progress: bool = True):
        """
        Initialize connection to SPX device.
        
        Args:
            port: Serial port name (e.g., '/dev/ttyACM1'). If None, auto-detect.
            show_progress: Whether to show progress indicators for transfers (default: True)
        """
        if port is None:
            port = self._find_spx_port()
        
        if port is None:
            raise USBFSException("Could not find SPX device. Make sure device is connected.")
        
        self.ser = serial.Serial(port, 115200, timeout=1)
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        
        # Drain any leftover input (binary data from failed transfers, etc.)
        # Read with short timeout until nothing more is available
        self.ser.timeout = 0.1  # Short timeout for draining
        while True:
            data = self.ser.read(4096)  # Read in chunks
            if len(data) == 0:
                break
        
        # Restore normal timeout
        self.ser.timeout = 1
        
        # Send STATUS command to verify connection is clean and ready
        response = self._send_command("STATUS")
        status, _ = self._parse_response(response)
        if status != "OK":
            raise USBFSIOError(f"Connection not ready: {response}")
        
        self.show_progress = show_progress and sys.stdout.isatty()
    
    def _find_spx_port(self) -> Optional[str]:
        """Find the SPX CDC port (second interface)"""
        return find_spx_port_by_interface(USBFS_INTERFACE)
    
    def _send_command(self, cmd: str) -> str:
        """Send command and read response line"""
        cmd_line = cmd + '\n'
        self.ser.write(cmd_line.encode('ascii'))
        self.ser.flush()
        
        response = self.ser.readline().decode('ascii', errors='ignore').strip()
        return response
    
    def _parse_response(self, response: str) -> Tuple[str, Optional[int]]:
        """Parse response line into status and optional value"""
        parts = response.split(' ', 1)
        status = parts[0]
        if len(parts) > 1:
            try:
                value = int(parts[1])
            except ValueError:
                # If it's not a pure integer, return None (e.g., "ERR 4 Unknown command")
                value = None
        else:
            value = None
        return status, value
    
    def _read_error(self, response: str) -> Tuple[int, str]:
        """Parse error response"""
        # Format: ERR <code> <message>
        parts = response.split(' ', 2)
        if len(parts) < 3:
            return 5, "Unknown error"
        code = int(parts[1])
        message = parts[2]
        return code, message
    
    def ls(self, path: str = "/") -> list:
        """
        List directory contents.
        
        Args:
            path: Directory path (default: "/")
            
        Returns:
            List of tuples: (type, name, size) where type is 'D' or 'F'
        """
        cmd = f"LS {path}"
        response = self._send_command(cmd)
        
        status, _ = self._parse_response(response)
        if status == "ERR":
            code, msg = self._read_error(response)
            if code == 1:
                raise USBFSNotFoundError(msg)
            raise USBFSIOError(msg)
        
        if status != "OK":
            raise USBFSIOError(f"Unexpected response: {response}")
        
        # Read directory listing lines
        entries = []
        while True:
            line = self.ser.readline().decode('ascii', errors='ignore').strip()
            if not line:
                break
            
            # Format: [D|F] <name> <size>
            parts = line.split(' ', 2)
            if len(parts) >= 2:
                entry_type = parts[0]
                name = parts[1]
                size = int(parts[2]) if len(parts) > 2 else 0
                entries.append((entry_type, name, size))
        
        return entries
    
    def _format_size(self, size: int) -> str:
        """Format size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def _show_progress(self, transferred: int, total: int, operation: str = "Transfer"):
        """Show progress indicator"""
        if not self.show_progress:
            return
        
        percent = (transferred / total * 100) if total > 0 else 0
        bar_width = 40
        filled = int(bar_width * transferred / total) if total > 0 else 0
        bar = '=' * filled + '-' * (bar_width - filled)
        
        transferred_str = self._format_size(transferred)
        total_str = self._format_size(total)
        
        # Use \r to overwrite the same line
        sys.stdout.write(f"\r{operation}: [{bar}] {percent:.1f}% ({transferred_str}/{total_str})")
        sys.stdout.flush()
    
    def get(self, remote_path: str, local_path: str):
        """
        Download file from RAMFS.
        
        Args:
            remote_path: Path on device
            local_path: Local file path
        """
        cmd = f"GET {remote_path}"
        response = self._send_command(cmd)
        
        status, file_size = self._parse_response(response)
        if status == "ERR":
            code, msg = self._read_error(response)
            if code == 1:
                raise USBFSNotFoundError(msg)
            raise USBFSIOError(msg)
        
        if status != "OK" or file_size is None:
            raise USBFSIOError(f"Unexpected response: {response}")
        
        if self.show_progress:
            print(f"Downloading {remote_path} -> {local_path} ({self._format_size(file_size)})")
        
        # Read binary data
        transferred = 0
        start_time = time.time()
        with open(local_path, 'wb') as f:
            remaining = file_size
            while remaining > 0:
                chunk_size = min(remaining, 4096)
                data = self.ser.read(chunk_size)
                if len(data) == 0:
                    raise USBFSIOError("Connection closed during transfer")
                f.write(data)
                transferred += len(data)
                remaining -= len(data)
                self._show_progress(transferred, file_size, "Downloading")
        
        if self.show_progress:
            elapsed = time.time() - start_time
            speed = transferred / elapsed if elapsed > 0 else 0
            print(f"\nDownloaded {self._format_size(transferred)} in {elapsed:.1f}s ({self._format_size(speed)}/s)")
    
    def put(self, local_path: str, remote_path: str):
        """
        Upload file to RAMFS.
        
        Args:
            local_path: Local file path
            remote_path: Path on device
        """
        file_size = os.path.getsize(local_path)
        cmd = f"PUT {remote_path} {file_size}\n"
        self.ser.write(cmd.encode('ascii'))
        self.ser.flush()
        
        if self.show_progress:
            print(f"Uploading {local_path} -> {remote_path} ({self._format_size(file_size)})")
        
        # Send binary data immediately after command
        transferred = 0
        start_time = time.time()
        with open(local_path, 'rb') as f:
            remaining = file_size
            while remaining > 0:
                chunk = f.read(4096)
                if not chunk:
                    break
                self.ser.write(chunk)
                self.ser.flush()
                transferred += len(chunk)
                remaining -= len(chunk)
                self._show_progress(transferred, file_size, "Uploading")
        
        if self.show_progress:
            elapsed = time.time() - start_time
            speed = transferred / elapsed if elapsed > 0 else 0
            print(f"\nUploaded {self._format_size(transferred)} in {elapsed:.1f}s ({self._format_size(speed)}/s)")
        
        # Read response after data transfer
        response = self.ser.readline().decode('ascii', errors='ignore').strip()
        status, _ = self._parse_response(response)
        if status == "ERR":
            code, msg = self._read_error(response)
            if code == 3:
                raise USBFSExistsError(msg)
            raise USBFSIOError(msg)
        if status != "OK":
            raise USBFSIOError(f"Unexpected response: {response}")
    
    def mv(self, old_path: str, new_path: str):
        """
        Move/rename file or directory.
        
        Args:
            old_path: Source path
            new_path: Destination path
        """
        cmd = f"MV {old_path} {new_path}"
        response = self._send_command(cmd)
        
        status, _ = self._parse_response(response)
        if status == "ERR":
            code, msg = self._read_error(response)
            if code == 1:
                raise USBFSNotFoundError(msg)
            if code == 3:
                raise USBFSExistsError(msg)
            raise USBFSIOError(msg)
        
        if status != "OK":
            raise USBFSIOError(f"Unexpected response: {response}")
    
    def rm(self, path: str):
        """
        Delete file.
        
        Args:
            path: File path
        """
        cmd = f"RM {path}"
        response = self._send_command(cmd)
        
        status, _ = self._parse_response(response)
        if status == "ERR":
            code, msg = self._read_error(response)
            if code == 1:
                raise USBFSNotFoundError(msg)
            raise USBFSIOError(msg)
        
        if status != "OK":
            raise USBFSIOError(f"Unexpected response: {response}")
    
    def mkdir(self, path: str):
        """
        Create directory.
        
        Args:
            path: Directory path
        """
        cmd = f"MKDIR {path}"
        response = self._send_command(cmd)
        
        status, _ = self._parse_response(response)
        if status == "ERR":
            code, msg = self._read_error(response)
            if code == 3:
                raise USBFSExistsError(msg)
            raise USBFSIOError(msg)
        
        if status != "OK":
            raise USBFSIOError(f"Unexpected response: {response}")
    
    def rmdir(self, path: str):
        """
        Remove directory.
        
        Args:
            path: Directory path
        """
        cmd = f"RMDIR {path}"
        response = self._send_command(cmd)
        
        status, _ = self._parse_response(response)
        if status == "ERR":
            code, msg = self._read_error(response)
            if code == 1:
                raise USBFSNotFoundError(msg)
            if code == 2:
                raise USBFSPermissionError(msg)
            raise USBFSIOError(msg)
        
        if status != "OK":
            raise USBFSIOError(f"Unexpected response: {response}")
    
    def reboot(self):
        """
        Trigger ZX Spectrum reboot.
        """
        cmd = "REBOOT"
        response = self._send_command(cmd)
        
        status, _ = self._parse_response(response)
        if status != "OK":
            raise USBFSIOError(f"Unexpected response: {response}")
    
    def autoboot(self):
        """
        Configure autoboot from xfs://ram/ and reboot ZX Spectrum.
        """
        cmd = "AUTOBOOT"
        response = self._send_command(cmd)
        
        status, _ = self._parse_response(response)
        if status == "ERR":
            code, msg = self._read_error(response)
            raise USBFSIOError(f"Error {code}: {msg}")
        if status != "OK":
            raise USBFSIOError(f"Unexpected response: {response}")
    
    def close(self):
        """Close connection"""
        if self.ser and self.ser.is_open:
            self.ser.close()


# Command-line interface functions
def cmd_ls(args, show_progress: bool = True):
    """List directory"""
    conn = SPXConnection(args.port, show_progress=show_progress)
    try:
        entries = conn.ls(args.path)
        for entry_type, name, size in entries:
            if entry_type == 'D':
                print(f"d {name:30s} {size:10d}")
            else:
                print(f"f {name:30s} {size:10d}")
    finally:
        conn.close()


def cmd_get(args, show_progress: bool = True):
    """Download file"""
    conn = SPXConnection(args.port, show_progress=show_progress)
    try:
        conn.get(args.remote, args.local)
        if not show_progress:
            print(f"Downloaded {args.remote} -> {args.local}")
    finally:
        conn.close()


def cmd_put(args, show_progress: bool = True):
    """Upload file"""
    conn = SPXConnection(args.port, show_progress=show_progress)
    try:
        conn.put(args.local, args.remote)
        if not show_progress:
            print(f"Uploaded {args.local} -> {args.remote}")
    finally:
        conn.close()


def cmd_mv(args, show_progress: bool = True):
    """Move/rename file"""
    conn = SPXConnection(args.port, show_progress=show_progress)
    try:
        conn.mv(args.old, args.new)
        print(f"Moved {args.old} -> {args.new}")
    finally:
        conn.close()


def cmd_rm(args, show_progress: bool = True):
    """Delete file"""
    conn = SPXConnection(args.port, show_progress=show_progress)
    try:
        conn.rm(args.path)
        print(f"Deleted {args.path}")
    finally:
        conn.close()


def cmd_mkdir(args, show_progress: bool = True):
    """Create directory"""
    conn = SPXConnection(args.port, show_progress=show_progress)
    try:
        conn.mkdir(args.path)
        print(f"Created directory {args.path}")
    finally:
        conn.close()


def cmd_rmdir(args, show_progress: bool = True):
    """Remove directory"""
    conn = SPXConnection(args.port, show_progress=show_progress)
    try:
        conn.rmdir(args.path)
        print(f"Removed directory {args.path}")
    finally:
        conn.close()


def cmd_reboot(args, show_progress: bool = True):
    """Trigger ZX Spectrum reboot"""
    conn = SPXConnection(args.port, show_progress=show_progress)
    try:
        conn.reboot()
        print("Reboot command sent")
    finally:
        conn.close()


def cmd_autoboot(args, show_progress: bool = True):
    """Configure autoboot from xfs://ram/ and reboot ZX Spectrum"""
    conn = SPXConnection(args.port, show_progress=show_progress)
    try:
        conn.autoboot()
        print("Autoboot configured and reboot command sent")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='SPX - Spectranext tool')
    parser.add_argument('--port', '-p', help='Serial port (auto-detect if not specified)')
    parser.add_argument('--no-progress', action='store_true', help='Disable progress indicators')
    
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # LS command
    parser_ls = subparsers.add_parser('ls', help='List directory')
    parser_ls.add_argument('path', nargs='?', default='/', help='Directory path')
    
    # GET command
    parser_get = subparsers.add_parser('get', help='Download file')
    parser_get.add_argument('remote', help='Remote file path')
    parser_get.add_argument('local', help='Local file path')
    
    # PUT command
    parser_put = subparsers.add_parser('put', help='Upload file')
    parser_put.add_argument('local', help='Local file path')
    parser_put.add_argument('remote', help='Remote file path')
    
    # MV command
    parser_mv = subparsers.add_parser('mv', help='Move/rename file')
    parser_mv.add_argument('old', help='Old path')
    parser_mv.add_argument('new', help='New path')
    
    # RM command
    parser_rm = subparsers.add_parser('rm', help='Delete file')
    parser_rm.add_argument('path', help='File path')
    
    # MKDIR command
    parser_mkdir = subparsers.add_parser('mkdir', help='Create directory')
    parser_mkdir.add_argument('path', help='Directory path')
    
    # RMDIR command
    parser_rmdir = subparsers.add_parser('rmdir', help='Remove directory')
    parser_rmdir.add_argument('path', help='Directory path')
    
    # REBOOT command
    parser_reboot = subparsers.add_parser('reboot', help='Trigger ZX Spectrum reboot')
    
    # AUTOBOOT command
    parser_autoboot = subparsers.add_parser('autoboot', help='Configure autoboot from xfs://ram/ and reboot ZX Spectrum')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        # Create connection with progress setting
        show_progress = not args.no_progress
        
        if args.command == 'ls':
            cmd_ls(args, show_progress)
        elif args.command == 'get':
            cmd_get(args, show_progress)
        elif args.command == 'put':
            cmd_put(args, show_progress)
        elif args.command == 'mv':
            cmd_mv(args, show_progress)
        elif args.command == 'rm':
            cmd_rm(args, show_progress)
        elif args.command == 'mkdir':
            cmd_mkdir(args, show_progress)
        elif args.command == 'rmdir':
            cmd_rmdir(args, show_progress)
        elif args.command == 'reboot':
            cmd_reboot(args, show_progress)
        elif args.command == 'autoboot':
            cmd_autoboot(args, show_progress)
    except USBFSNotFoundError as e:
        print(f"Error: Not found - {e}", file=sys.stderr)
        sys.exit(1)
    except USBFSPermissionError as e:
        print(f"Error: Permission denied - {e}", file=sys.stderr)
        sys.exit(1)
    except USBFSExistsError as e:
        print(f"Error: Already exists - {e}", file=sys.stderr)
        sys.exit(1)
    except USBFSInvalidError as e:
        print(f"Error: Invalid - {e}", file=sys.stderr)
        sys.exit(1)
    except USBFSIOError as e:
        print(f"Error: I/O error - {e}", file=sys.stderr)
        sys.exit(1)
    except USBFSException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

