#!/usr/bin/env python3
"""
SPX - Spectranext tool
Provides binutils-style commands for browsing and managing RAMFS over USB CDC.
"""

import sys
import os
import serial
import serial.tools.list_ports
import argparse
import time
import socket
import tempfile
import json
import binascii
from typing import Optional, Tuple

# Import device detection from spectranext-detect.py
# Use importlib to handle relative imports
import importlib.util
_detect_path = os.path.join(os.path.dirname(__file__), 'spectranext-detect.py')
_spec = importlib.util.spec_from_file_location('spectranext_detect', _detect_path)
_spectranext_detect = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_spectranext_detect)
find_spectranext_devices = _spectranext_detect.find_spectranext_devices

# CDC interface numbers (0 = console, 1 = USBFS, 2 = GDB)
USBFS_INTERFACE = 1


def find_spx_port_by_interface(interface: int = 1) -> Optional[str]:
    """
    Find SPX port by interface number.
    
    Args:
        interface: Interface number (0 = console/cli, 1 = USBFS)
    
    Returns:
        Port device path or None if not found
    """
    devices, _ = find_spectranext_devices()
    
    if interface == 0:
        return devices.get('cli')
    elif interface == 1:
        return devices.get('usbfs')
    
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
        
        self.port = port
        
        # Get USB device info if available
        self.usb_info = None
        try:
            devices, serial_number = find_spectranext_devices()
            for dev_type, dev_port in devices.items():
                if dev_port == port:
                    self.usb_info = {
                        "port": port,
                        "type": dev_type,
                        "serial": serial_number
                    }
                    break
        except:
            pass
        
        self.ser = serial.Serial(port, 115200, timeout=1)
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        
        # Initialize request ID counter
        self._request_id = 1
        
        # Drain any leftover input (binary data from failed transfers, etc.)
        # Read with short timeout until nothing more is available
        self.ser.timeout = 0.1  # Short timeout for draining
        while True:
            data = self.ser.read(4096)  # Read in chunks
            if len(data) == 0:
                break
        
        # Restore normal timeout
        self.ser.timeout = 1
        
        # Drain input buffer before sending STATUS to ensure clean state
        self._drain_input()
        
        # Send STATUS JSON-RPC request to verify connection is clean and ready
        # Retry a few times in case device is busy
        max_retries = 3
        status_result = None
        for attempt in range(max_retries):
            try:
                status_result = self._send_jsonrpc_request("status", {})
                break
            except (serial.SerialTimeoutException, serial.SerialException) as e:
                if attempt < max_retries - 1:
                    time.sleep(0.1)  # Brief delay before retry
                    continue
                raise USBFSIOError(f"Connection error: {e}")
        
        self.show_progress = show_progress and sys.stdout.isatty()
    
    def _drain_input(self):
        """Drain any leftover data from input buffer"""
        # Temporarily set short timeout for draining
        old_timeout = self.ser.timeout
        self.ser.timeout = 0.1
        try:
            while True:
                try:
                    data = self.ser.read(4096)  # Read in chunks
                    if len(data) == 0:
                        break
                except serial.serialutil.SerialException as e:
                    # Ignore "device reports readiness to read but returned no data" errors
                    # This can happen during draining when device is busy or disconnected
                    if "device reports readiness to read but returned no data" in str(e):
                        break
                    # Re-raise other serial exceptions
                    raise
        finally:
            # Restore original timeout
            self.ser.timeout = old_timeout
    
    def _find_spx_port(self) -> Optional[str]:
        """Find the SPX CDC port (second interface)"""
        return find_spx_port_by_interface(USBFS_INTERFACE)
    
    def _send_jsonrpc_request(self, method: str, params: dict) -> dict:
        """Send JSON-RPC request and return result"""
        request_id = self._request_id
        self._request_id += 1
        
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": request_id
        }
        
        request_json = json.dumps(request) + '\n'
        self.ser.write(request_json.encode('utf-8'))
        self.ser.flush()
        
        # Read response line
        response_line = self.ser.readline().decode('utf-8', errors='ignore').strip()
        if not response_line:
            raise USBFSIOError("No response received")
        
        try:
            response = json.loads(response_line)
        except json.JSONDecodeError as e:
            raise USBFSIOError(f"Invalid JSON response: {e}")
        
        # Check for JSON-RPC error
        if "error" in response:
            error = response["error"]
            error_code = error.get("code")
            error_message = error.get("message", "Unknown error")
            error_data = error.get("data", {})
            
            # Extract file error code if present
            file_error = error_data.get("file_error")
            if file_error == 1:
                raise USBFSNotFoundError(error_data.get("message", error_message))
            elif file_error == 2:
                raise USBFSPermissionError(error_data.get("message", error_message))
            elif file_error == 3:
                raise USBFSExistsError(error_data.get("message", error_message))
            elif file_error == 4:
                raise USBFSInvalidError(error_data.get("message", error_message))
            elif file_error == 5:
                raise USBFSIOError(error_data.get("message", error_message))
            else:
                raise USBFSIOError(f"{error_message} (code: {error_code})")
        
        # Return result
        if "result" not in response:
            raise USBFSIOError("No result in response")
        
        return response["result"]
    
    def ls(self, path: str = "/") -> list:
        """
        List directory contents.
        
        Args:
            path: Directory path (default: "/")
            
        Returns:
            List of tuples: (type, name, size) where type is 'D' or 'F'
        """
        result = self._send_jsonrpc_request("ls", {"path": path})
        
        entries = []
        for entry in result.get("entries", []):
            entry_type = entry.get("type", "F")
            name = entry.get("name", "")
            size = entry.get("size", 0) if entry_type == "F" else 0
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
        Download file from RAMFS using chunked JSON-RPC protocol.
        
        Args:
            remote_path: Path on device
            local_path: Local file path
        """
        # Start GET operation
        result = self._send_jsonrpc_request("get", {"path": remote_path})
        file_size = int(result.get("size", 0))
        chunk_size = int(result.get("chunk_size", 8192))
        
        if self.show_progress:
            print(f"Downloading {remote_path} -> {local_path} ({self._format_size(file_size)})")
        
        # Request chunks until we have all data
        transferred = 0
        start_time = time.time()
        offset = 0
        
        with open(local_path, 'wb') as f:
            while offset < file_size:
                chunk_request_size = min(chunk_size, file_size - offset)
                
                # Request chunk
                chunk_result = self._send_jsonrpc_request("get_chunk", {
                    "offset": offset,
                    "size": chunk_request_size
                })
                
                # Decode hex data
                data_hex = chunk_result.get("data", "")
                chunk_data = binascii.unhexlify(data_hex)
                chunk_received = len(chunk_data)
                
                f.write(chunk_data)
                transferred += chunk_received
                offset += chunk_received
                self._show_progress(transferred, file_size, "Downloading")
        
        if self.show_progress:
            elapsed = time.time() - start_time
            speed = transferred / elapsed if elapsed > 0 else 0
            print(f"\nDownloaded {self._format_size(transferred)} in {elapsed:.1f}s ({self._format_size(speed)}/s)")
    
    def put(self, local_path: str, remote_path: str):
        """
        Upload file to RAMFS using chunked JSON-RPC protocol.
        
        Args:
            local_path: Local file path
            remote_path: Path on device
        """
        file_size = os.path.getsize(local_path)
        
        # Start PUT operation
        result = self._send_jsonrpc_request("put", {
            "path": remote_path,
            "size": file_size
        })
        max_chunk_size = int(result.get("chunk_size", 8192))
        
        if self.show_progress:
            print(f"Uploading {local_path} -> {remote_path} ({self._format_size(file_size)})")
        
        # Send binary data in chunks
        transferred = 0
        start_time = time.time()
        with open(local_path, 'rb') as f:
            offset = 0
            while offset < file_size:
                chunk_size = min(max_chunk_size, file_size - offset)
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                
                # Hex encode chunk
                chunk_hex = binascii.hexlify(chunk).decode('ascii')
                
                # Send chunk
                chunk_result = self._send_jsonrpc_request("put_chunk", {
                    "data": chunk_hex,
                    "offset": offset
                })
                
                bytes_received = int(chunk_result.get("received", 0))
                transferred = bytes_received
                offset += len(chunk)
                self._show_progress(transferred, file_size, "Uploading")
        
        # Complete PUT operation
        self._send_jsonrpc_request("put_complete", {})
        
        if self.show_progress:
            elapsed = time.time() - start_time
            speed = transferred / elapsed if elapsed > 0 else 0
            print(f"\nUploaded {self._format_size(transferred)} in {elapsed:.1f}s ({self._format_size(speed)}/s)")
    
    def mv(self, old_path: str, new_path: str):
        """
        Move/rename file or directory.
        
        Args:
            old_path: Source path
            new_path: Destination path
        """
        self._send_jsonrpc_request("mv", {
            "old_path": old_path,
            "new_path": new_path
        })
    
    def rm(self, path: str):
        """
        Delete file.
        
        Args:
            path: File path
        """
        self._send_jsonrpc_request("rm", {"path": path})
    
    def mkdir(self, path: str):
        """
        Create directory.
        
        Args:
            path: Directory path
        """
        self._send_jsonrpc_request("mkdir", {"path": path})
    
    def rmdir(self, path: str):
        """
        Remove directory.
        
        Args:
            path: Directory path
        """
        self._send_jsonrpc_request("rmdir", {"path": path})
    
    def reboot(self):
        """
        Trigger ZX Spectrum reboot.
        """
        self._send_jsonrpc_request("reboot", {})
    
    def autoboot(self):
        """
        Configure autoboot from xfs://ram/ and reboot ZX Spectrum.
        """
        self._send_jsonrpc_request("autoboot", {})
    
    def close(self):
        """Close connection"""
        if self.ser and self.ser.is_open:
            self.ser.close()


    def __enter__(self):
        """Context manager entry"""
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.release()


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


def find_free_port(start_port: int = 8000) -> int:
    """Find a free port starting from start_port"""
    port = start_port
    while port < start_port + 100:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('127.0.0.1', port))
            sock.close()
            return port
        except OSError:
            port += 1
    raise RuntimeError(f"Could not find free port starting from {start_port}")


def cmd_browser(args, show_progress: bool = True):
    """Start web browser interface for RAMFS"""
    # Import spx-browser module and run it
    # Use importlib to handle the hyphenated module name
    import importlib.util
    script_dir = os.path.dirname(os.path.abspath(__file__))
    browser_path = os.path.join(script_dir, 'spx-browser.py')
    spec = importlib.util.spec_from_file_location("spx_browser", browser_path)
    browser_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(browser_module)
    browser_module.main()


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
    
    # BROWSER command
    parser_browser = subparsers.add_parser('browser', help='Start web browser interface for RAMFS')
    parser_browser.add_argument('--port', type=int, help='Port to listen on (default: auto-detect)')
    parser_browser.add_argument('--host', type=str, default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Create connection with progress setting
    show_progress = not args.no_progress
    
    try:
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
        elif args.command == 'browser':
            cmd_browser(args, show_progress)
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
