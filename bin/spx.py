#!/usr/bin/env python3
"""
SPX - Spectranext tool
Provides binutils-style commands for browsing and managing RAMFS over GDB Remote Serial Protocol (RSP).
"""

import sys
import os
import serial
import socket
import argparse
import time
import binascii
import threading
import queue
import signal
import errno
from typing import Optional, Tuple, List

# fcntl is Unix-only, not available on Windows
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

# msvcrt provides file locking on Windows
try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

# Import device detection from spectranext-detect.py
import importlib.util
_detect_path = os.path.join(os.path.dirname(__file__), 'spectranext-detect.py')
_spec = importlib.util.spec_from_file_location('spectranext_detect', _detect_path)
_spectranext_detect = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_spectranext_detect)
find_spectranext_device = _spectranext_detect.find_spectranext_device


# Exception classes
class RSPException(Exception):
    """Base exception for RSP errors"""
    pass


class RSPNotSupportedError(RSPException):
    """vSpectranext not supported"""
    pass


class RSPIOError(RSPException):
    """I/O error"""
    pass


class RSPNotFoundError(RSPException):
    """File or directory not found"""
    pass


class RSPPermissionError(RSPException):
    """Permission denied"""
    pass


class RSPExistsError(RSPException):
    """Already exists"""
    pass


class RSPInvalidError(RSPException):
    """Invalid parameter"""
    pass


class SPXConnection:
    """Connection to SPX device using RSP protocol"""
    
    def __init__(self, port: Optional[str] = None, show_progress: bool = True, verbose: bool = False):
        """
        Initialize connection to SPX device.
        
        Args:
            port: Serial port name (e.g., '/dev/ttyACM0') or TCP address (e.g., 'localhost:1337').
                  If None, auto-detect USB first, then fall back to localhost:1337.
            show_progress: Whether to show progress indicators for transfers (default: True)
            verbose: Whether to log all data sent and received (default: False)
        """
        self.is_tcp = False
        self.ser = None
        self.sock = None
        self.port = None  # Initialize to None, will be set below
        self._lock_file = None
        self._lock_fd = None
        
        # Set flags before any operations that might use them
        self.show_progress = show_progress and sys.stdout.isatty()
        self.verbose = verbose
        
        # Determine connection type
        if port:
            # Check if port looks like TCP address (host:port or just port number)
            if ':' in port or port.isdigit():
                self.is_tcp = True
                self.port = port
            else:
                self.is_tcp = False
                self.port = port
        else:
            # Try environment variable first
            env_port = os.environ.get('SPECTRANEXT_CLI')
            if env_port:
                if ':' in env_port or env_port.isdigit():
                    self.is_tcp = True
                    self.port = env_port
                else:
                    self.is_tcp = False
                    self.port = env_port
            else:
                # Auto-detect: try USB first
                try:
                    detected_port, _ = find_spectranext_device()
                    if detected_port:
                        self.is_tcp = False
                        self.port = detected_port
                    else:
                        # Fall back to TCP
                        self.is_tcp = True
                        self.port = "localhost:1337"
                        if self.verbose:
                            print("[INFO] No USB device found, falling back to TCP (localhost:1337)", file=sys.stderr)
                except Exception as e:
                    # USB detection failed, fall back to TCP
                    if self.verbose:
                        print(f"[INFO] USB detection failed ({e}), falling back to TCP (localhost:1337)", file=sys.stderr)
                    self.is_tcp = True
                    self.port = "localhost:1337"
        
        # Only raise exception if port is still not set (shouldn't happen after auto-detect fallback)
        if not self.port:
            raise RSPException("Could not find SPX device. Make sure device is connected (USB) or GDB server is running (TCP).")
        
        if self.verbose:
            connection_type = "TCP" if self.is_tcp else "USB"
            print(f"[INFO] Connecting via {connection_type} to {self.port}", file=sys.stderr)
        
        # Connect based on type
        if self.is_tcp:
            self._connect_tcp()
        else:
            self._connect_usb()
        
        # Default packet size (will be updated from qSupported response)
        self.max_packet_size = 1024
        
        # Queue for storing response packets (non-O packets) and ACK/NAK
        self._response_queue = queue.Queue()
        
        # O-packet callback for streaming output
        self._o_packet_callback = None
        
        # Thread control
        self._reader_thread = None
        self._reader_stop = threading.Event()
        
        # Drain any leftover input (console prompts, etc.)
        self._drain_input()
        
        # Start background reader thread
        self._start_reader_thread()
        
        # Verify vSpectranext support and parse packet size
        self._verify_support()
    
    def _connect_tcp(self):
        """Connect via TCP socket"""
        # Parse host:port
        if ':' in self.port:
            host, port_str = self.port.rsplit(':', 1)
            try:
                port = int(port_str)
            except ValueError:
                raise RSPException(f"Invalid TCP port: {port_str}")
        else:
            # Just port number
            try:
                port = int(self.port)
                host = 'localhost'
            except ValueError:
                raise RSPException(f"Invalid TCP address: {self.port}")
        
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(1)  # 1 second timeout for connect
            self.sock.connect((host, port))
            self.sock.settimeout(1)  # 1 second timeout for read/write
            if self.verbose:
                print(f"[TCP] Connected to {host}:{port}", file=sys.stderr)
        except (socket.error, OSError) as e:
            error_msg = str(e)
            if "Connection refused" in error_msg or "errno 61" in error_msg:
                raise RSPException(f"Failed to connect to {host}:{port}: Connection refused. Make sure GDB server is running on port {port}.")
            elif "timed out" in error_msg.lower() or "errno 60" in error_msg:
                raise RSPException(f"Failed to connect to {host}:{port}: Connection timed out. Make sure GDB server is running on port {port}.")
            else:
                raise RSPException(f"Failed to connect to {host}:{port}: {e}")
    
    def _connect_usb(self):
        """Connect via USB serial"""
        # Acquire exclusive lock on the serial port device file
        if HAS_FCNTL:
            # Unix: lock the device file directly
            try:
                # Open lock file (the device file itself)
                self._lock_fd = os.open(self.port, os.O_RDWR)
                # Try to acquire exclusive lock (non-blocking first)
                try:
                    fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except IOError as e:
                    if e.errno == errno.EWOULDBLOCK:
                        # Lock is held by another process - wait for it
                        if self.verbose:
                            print(f"[LOCK] Waiting for device lock on {self.port}...", file=sys.stderr)
                        # Block until lock is available
                        fcntl.flock(self._lock_fd, fcntl.LOCK_EX)
                        if self.verbose:
                            print(f"[LOCK] Acquired device lock on {self.port}", file=sys.stderr)
                    else:
                        os.close(self._lock_fd)
                        self._lock_fd = None
                        raise RSPException(f"Failed to acquire lock on {self.port}: {e}")
            except OSError as e:
                if self._lock_fd is not None:
                    os.close(self._lock_fd)
                    self._lock_fd = None
                raise RSPException(f"Failed to open device file {self.port} for locking: {e}")
        elif HAS_MSVCRT:
            # Windows: create a lock file and lock it
            import tempfile
            # Create lock file path based on port name (e.g., COM28 -> spx_COM28.lock)
            # Sanitize port name for use in filename
            sanitized_port = self.port.replace(':', '_').replace('\\', '_').replace('/', '_')
            lock_name = f"spx_{sanitized_port}.lock"
            lock_dir = tempfile.gettempdir()
            self._lock_file = os.path.join(lock_dir, lock_name)
            
            try:
                # Try to acquire lock with retries
                max_retries = 100  # Wait up to 10 seconds (100 * 0.1s)
                retry_count = 0
                lock_acquired = False
                
                while retry_count < max_retries and not lock_acquired:
                    try:
                        # Open or create lock file
                        self._lock_fd = os.open(self._lock_file, os.O_CREAT | os.O_RDWR)
                        # Try to lock byte 0 (non-blocking)
                        try:
                            msvcrt.locking(self._lock_fd, msvcrt.LK_NBLCK, 1)
                            lock_acquired = True
                            if self.verbose:
                                print(f"[LOCK] Acquired device lock on {self.port}", file=sys.stderr)
                        except OSError as lock_err:
                            # Lock is held by another process
                            os.close(self._lock_fd)
                            self._lock_fd = None
                            if self.verbose and retry_count == 0:
                                print(f"[LOCK] Waiting for device lock on {self.port}...", file=sys.stderr)
                            time.sleep(0.1)
                            retry_count += 1
                    except OSError as e:
                        if self._lock_fd is not None:
                            try:
                                os.close(self._lock_fd)
                            except:
                                pass
                            self._lock_fd = None
                        if self.verbose and retry_count == 0:
                            print(f"[LOCK] Waiting for device lock on {self.port}...", file=sys.stderr)
                        time.sleep(0.1)
                        retry_count += 1
                
                if not lock_acquired:
                    raise RSPException(f"Failed to acquire lock on {self.port}: timeout waiting for lock")
            except OSError as e:
                if self._lock_fd is not None:
                    try:
                        msvcrt.locking(self._lock_fd, msvcrt.LK_UNLCK, 1)
                        os.close(self._lock_fd)
                    except:
                        pass
                    self._lock_fd = None
                raise RSPException(f"Failed to create lock file for {self.port}: {e}")
        
        # Now open the serial port (pyserial will open it again, but that's fine)
        try:
            self.ser = serial.Serial(self.port, 115200, timeout=1, write_timeout=1)
        except serial.SerialException as e:
            # Release lock if serial open fails
            if HAS_FCNTL and self._lock_fd is not None:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                os.close(self._lock_fd)
                self._lock_fd = None
            elif HAS_MSVCRT and self._lock_fd is not None:
                msvcrt.locking(self._lock_fd, msvcrt.LK_UNLCK, 1)
                os.close(self._lock_fd)
                try:
                    os.unlink(self._lock_file)
                except:
                    pass
                self._lock_fd = None
                self._lock_file = None
            raise RSPException(f"Failed to open serial port {self.port}: {e}")
        
        # Give device time to stabilize
        time.sleep(0.1)
        
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
    
    def _read(self, size: int = 1) -> bytes:
        """Read data from connection (USB or TCP)"""
        if self.is_tcp:
            try:
                return self.sock.recv(size)
            except socket.timeout:
                return b''
            except socket.error as e:
                raise RSPIOError(f"TCP read error: {e}")
        else:
            return self.ser.read(size)
    
    def _write(self, data: bytes) -> None:
        """Write data to connection (USB or TCP)"""
        if self.is_tcp:
            try:
                self.sock.sendall(data)
            except socket.error as e:
                raise RSPIOError(f"TCP write error: {e}")
        else:
            self.ser.write(data)
            self.ser.flush()
    
    def _flush(self) -> None:
        """Flush output buffer (USB only, TCP doesn't need flushing)"""
        if not self.is_tcp:
            self.ser.flush()
    
    def _drain_input(self):
        """Drain any leftover data from input buffer"""
        if self.is_tcp:
            # For TCP, set a short timeout and read until nothing comes
            old_timeout = self.sock.gettimeout()
            self.sock.settimeout(0.1)
            try:
                while True:
                    try:
                        data = self.sock.recv(4096)
                        if len(data) == 0:
                            break
                    except socket.timeout:
                        break
            finally:
                self.sock.settimeout(old_timeout)
        else:
            old_timeout = self.ser.timeout
            self.ser.timeout = 0.1
            try:
                while True:
                    try:
                        data = self.ser.read(4096)
                        if len(data) == 0:
                            break
                    except serial.serialutil.SerialException as e:
                        if "device reports readiness to read but returned no data" in str(e):
                            break
                        raise
            finally:
                self.ser.timeout = old_timeout
    
    def _start_reader_thread(self):
        """Start background thread for reading RSP packets"""
        self._reader_stop.clear()
        self._reader_thread = threading.Thread(target=self._reader_thread_func, daemon=True)
        self._reader_thread.start()
    
    def _reader_thread_func(self):
        """Background thread function that continuously reads packets"""
        while not self._reader_stop.is_set():
            try:
                # Read a packet (with timeout to allow checking stop event)
                packet = self._read_packet_from_stream()
                if packet is None:
                    continue  # Timeout or error, continue loop
                
                # Check if it's O-packet (log output)
                if (len(packet) > 2) and packet.startswith('O'):
                    # Decode and handle O packet
                    log_msg = self._decode_o_packet(packet)
                    if log_msg:
                        if self._o_packet_callback:
                            # Call custom callback for streaming
                            self._o_packet_callback(log_msg)
                        else:
                            print(f"[LOG] {log_msg}", file=sys.stderr, end="")
                else:
                    # Non-O packet, put it in the queue
                    self._response_queue.put(packet)
            except RSPIOError as e:
                # Timeout or connection error - check if we should stop
                if self._reader_stop.is_set():
                    break
                # Otherwise, continue reading
                continue
            except Exception as e:
                # If we're shutting down, ignore errors (port might be closed)
                if self._reader_stop.is_set():
                    break
                # Unexpected error - log and continue
                if self.verbose:
                    print(f"[ERROR] Reader thread error: {e}", file=sys.stderr)
                continue
    
    def _read_packet_from_stream(self) -> Optional[str]:
        """
        Read a single RSP packet from the stream (used by reader thread).
        Returns None on timeout (non-blocking).
        """
        # Read first character - check for ACK/NAK or packet start
        while True:
            if self._reader_stop.is_set():
                return None
            
            try:
                b = self._read(1)
            except (serial.serialutil.SerialException, OSError, socket.error) as e:
                # If shutting down, return None silently
                if self._reader_stop.is_set():
                    return None
                if "device reports readiness to read but returned no data" in str(e):
                    return None  # Timeout, return None
                # Bad file descriptor usually means port/socket was closed during shutdown
                if "Bad file descriptor" in str(e) or "bad file descriptor" in str(e):
                    return None
                if isinstance(e, socket.timeout):
                    return None  # TCP timeout
                raise
            
            if len(b) == 0:
                return None  # Timeout
            
            # Check for ACK/NAK
            if b == b'+':
                if self.verbose:
                    print(f"< + (ack)", file=sys.stderr)
                return '+'  # ACK
            elif b == b'-':
                if self.verbose:
                    print(f"< - (nak)", file=sys.stderr)
                return '-'  # NAK
            elif b == b'$':
                break  # Start of RSP packet
            # Otherwise, skip and continue (might be noise)
        
        # Read packet data until '#'
        data = bytearray()
        while True:
            if self._reader_stop.is_set():
                return None
            
            try:
                b = self._read(1)
            except (serial.serialutil.SerialException, OSError, socket.error) as e:
                # If shutting down, return None silently
                if self._reader_stop.is_set():
                    return None
                if "device reports readiness to read but returned no data" in str(e):
                    return None  # Timeout
                # Bad file descriptor usually means port/socket was closed during shutdown
                if "Bad file descriptor" in str(e) or "bad file descriptor" in str(e):
                    return None
                if isinstance(e, socket.timeout):
                    return None  # TCP timeout
                raise
            
            if len(b) == 0:
                return None  # Timeout
            if b == b'#':
                break
            data.append(b[0])
        
        # Read checksum (2 hex digits)
        try:
            checksum_hex = self._read(2)
        except (serial.serialutil.SerialException, OSError, socket.error) as e:
            # If shutting down, return None silently
            if self._reader_stop.is_set():
                return None
            if "device reports readiness to read but returned no data" in str(e):
                return None  # Timeout
            # Bad file descriptor usually means port/socket was closed during shutdown
            if "Bad file descriptor" in str(e) or "bad file descriptor" in str(e):
                return None
            if isinstance(e, socket.timeout):
                return None  # TCP timeout
            raise
        
        if len(checksum_hex) != 2:
            return None  # Incomplete checksum
        
        # Verify checksum
        expected_checksum = int(checksum_hex.decode('ascii'), 16)
        actual_checksum = self._calculate_checksum(data)
        
        # Hex encoding is ASCII-safe
        packet_str = data.decode('ascii', errors='replace')
        
        if expected_checksum != actual_checksum:
            # Send NAK
            if self.verbose:
                print(f"< ${packet_str}#{checksum_hex.decode('ascii')} (checksum mismatch)", file=sys.stderr)
                print(f"> -", file=sys.stderr)
            self._write(b'-')
            return None  # Don't raise, just return None
        
        # Send ACK
        if self.verbose:
            print(f"< ${packet_str}#{checksum_hex.decode('ascii')}", file=sys.stderr)
            print(f"> +", file=sys.stderr)
        self._write(b'+')

        return packet_str
    
    def _read_ack_nak(self) -> bool:
        """Read ACK/NAK from queue"""
        try:
            response = self._response_queue.get(timeout=5.0)
            if response == '+':
                return True  # ACK
            elif response == '-':
                return False  # NAK
            else:
                raise RSPIOError(f"Unexpected response while waiting for ACK/NAK: {response}")
        except queue.Empty:
            raise RSPIOError("Timeout waiting for ACK/NAK")
    
    def _calculate_checksum(self, data: bytes) -> int:
        """Calculate RSP checksum (sum of bytes mod 256)"""
        return sum(data) % 256
    
    def _encode_binary_escaped(self, data: bytes) -> bytes:
        """Encode binary data with RSP escaping"""
        result = bytearray()
        for b in data:
            if b in (ord('}'), ord('#'), ord('$'), ord('*')):
                result.append(ord('}'))
                result.append(b ^ 0x20)
            else:
                result.append(b)
        return bytes(result)
    
    def _decode_binary_escaped(self, data: bytes) -> bytes:
        """Decode binary-escaped data"""
        result = bytearray()
        i = 0
        while i < len(data):
            b = data[i]
            if b == ord('}'):
                if i + 1 < len(data):
                    result.append(data[i + 1] ^ 0x20)
                    i += 2
                else:
                    # Invalid escape sequence
                    break
            else:
                result.append(b)
                i += 1
        return bytes(result)
    
    def _encode_path(self, path: str) -> str:
        """Encode path as ASCII-hex"""
        return binascii.hexlify(path.encode('utf-8')).decode('ascii')
    
    def _decode_path(self, hex_str: str) -> str:
        """Decode ASCII-hex path"""
        return binascii.unhexlify(hex_str).decode('utf-8')
    
    def _send_packet(self, packet: str) -> None:
        """Send RSP packet and wait for ACK/NAK"""
        # Hex encoding is ASCII-safe, so we can use ascii encoding
        data = packet.encode('ascii')
        checksum = self._calculate_checksum(data)
        packet_bytes = f"${packet}#{checksum:02x}".encode('ascii')
        
        if self.verbose:
            print(f"> {packet_bytes.decode('ascii', errors='replace')}", file=sys.stderr)
        
        # Retry on NAK
        max_retries = 3
        for attempt in range(max_retries):
            self._write(packet_bytes)
            
            # Read ACK/NAK (skip any leading '$' characters)
            try:
                ack_received = self._read_ack_nak()
                # Note: _read_ack_nak already prints verbose output, so we don't need to print again
                if ack_received:
                    return  # ACK received
                else:
                    if attempt < max_retries - 1:
                        continue  # Retry on NAK
                    raise RSPIOError("NAK received after retries")
            except RSPIOError as e:
                if attempt < max_retries - 1:
                    # Might be leftover data, drain and retry
                    self._drain_input()
                    continue
                raise
        
        raise RSPIOError("Failed to send packet after retries")
    
    def _send_packet_with_response(self, packet: str, timeout: Optional[float] = 5.0) -> str:
        """Send packet and return response payload"""
        self._send_packet(packet)
        return self._read_response(timeout=timeout)
    
    def _decode_o_packet(self, packet: str) -> str:
        """Decode O packet (log output) - hex-encoded text"""
        if not packet.startswith('O'):
            return ""
        
        hex_data = packet[1:]
        try:
            decoded = binascii.unhexlify(hex_data).decode('utf-8', errors='replace')
            return decoded
        except Exception:
            return ""
    
    def _read_response(self, timeout: Optional[float] = 5.0) -> str:
        """
        Read RSP response packet from queue (O packets are already handled by reader thread).
        Skips any ACK/NAK that might be in the queue (those are handled by _read_ack_nak).
        
        Args:
            timeout: Timeout in seconds to wait for response. If None, wait forever.
            
        Returns:
            Response packet payload
        """
        start_time = time.time()
        while True:
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    raise RSPIOError("Timeout waiting for response")
                remaining_timeout = timeout - elapsed
            else:
                # No timeout - wait forever
                remaining_timeout = None
            
            try:
                packet = self._response_queue.get(timeout=remaining_timeout)
                # Skip ACK/NAK - those are handled by _read_ack_nak
                if packet == '+' or packet == '-':
                    continue
                # This is the actual response packet
                return packet
            except queue.Empty:
                if timeout is not None:
                    raise RSPIOError("Timeout waiting for response")
                # If timeout is None, continue waiting (shouldn't happen, but be safe)
                continue
    
    def _verify_support(self):
        """Verify vSpectranext support via qSupported and parse packet size"""
        response = self._send_packet_with_response("qSupported")
        if "vSpectranext+" not in response:
            raise RSPNotSupportedError("Device does not support vSpectranext protocol")
        
        # Parse PacketSize from response (format: "PacketSize=1000;..." where 1000 is hex)
        if "PacketSize=" in response:
            try:
                # Extract PacketSize value
                parts = response.split(";")
                for part in parts:
                    if part.startswith("PacketSize="):
                        packet_size_hex = part.split("=")[1]
                        # Parse as hex (as per GDB RSP spec)
                        self.max_packet_size = int(packet_size_hex, 16)
                        if self.verbose:
                            print(f"[INFO] Using packet size: {self.max_packet_size} (0x{packet_size_hex})", file=sys.stderr)
                        break
            except (ValueError, IndexError) as e:
                # If parsing fails, use default
                if self.verbose:
                    print(f"[WARN] Failed to parse PacketSize from '{response}', using default 1024: {e}", file=sys.stderr)
    
    def _parse_errno(self, response: str) -> int:
        """Parse errno from response (F-1,<errno> or E<errno>)"""
        if response.startswith("F-1,"):
            return int(response[4:])
        elif response.startswith("E"):
            return int(response[1:])
        return 0
    
    def _raise_error(self, errno: int, message: str = ""):
        """Raise appropriate exception based on errno"""
        if errno == 2:  # ENOENT
            raise RSPNotFoundError(message or "File or directory not found")
        elif errno == 5:  # EIO
            raise RSPIOError(message or "I/O error")
        elif errno == 13:  # EACCES
            raise RSPPermissionError(message or "Permission denied")
        elif errno == 17:  # EEXIST
            raise RSPExistsError(message or "Already exists")
        elif errno == 22:  # EINVAL
            raise RSPInvalidError(message or "Invalid parameter")
        else:
            raise RSPIOError(message or f"I/O error (errno: {errno})")
    
    # vFile operations
    def _vfile_open(self, path: str, flags: int, mode: int) -> int:
        """Open file via vFile:open"""
        hex_path = self._encode_path(path)
        # Format: vFile:open:<fd>,<flags>,<mode>,<path>
        # fd is ignored by firmware but required in protocol
        packet = f"vFile:open:0,{flags:x},{mode:x},{hex_path}"
        response = self._send_packet_with_response(packet)
        
        if response.startswith("F-1,"):
            errno = self._parse_errno(response)
            self._raise_error(errno, f"Failed to open {path}")
        
        # Parse F<fd>
        if not response.startswith("F"):
            raise RSPIOError(f"Unexpected response: {response}")
        
        fd_hex = response[1:]
        return int(fd_hex, 16)
    
    def _vfile_close(self, fd: int) -> None:
        """Close file via vFile:close"""
        packet = f"vFile:close:{fd:x}"
        response = self._send_packet_with_response(packet)
        
        if response.startswith("F-1,"):
            errno = self._parse_errno(response)
            self._raise_error(errno, "Failed to close file")
        
        if response != "F0":
            raise RSPIOError(f"Unexpected response: {response}")
    
    def _vfile_pread(self, fd: int, count: int) -> bytes:
        """Read from file via vFile:pread (sequential read, no offset)"""
        # Limit count to fit in RSP packet (account for hex encoding overhead)
        # Response format: hex data only (2 hex digits per byte, no count prefix)
        # Need space for:
        #   - Hex data (count * 2 bytes)
        #   - Null terminator (1 byte)
        # Max: (count * 2) + 1 <= max_packet_size, so count <= (max_packet_size - 1) / 2
        max_binary = (self.max_packet_size - 1) // 2  # Reserve 1 byte for null terminator
        if count > max_binary:
            count = max_binary
        
        packet = f"vFile:pread:{fd:x},{count:x}"
        response = self._send_packet_with_response(packet)
        
        if response.startswith("F-1,"):
            errno = self._parse_errno(response)
            self._raise_error(errno, "Failed to read file")
        
        # Parse hex data (no count prefix, just hex data)
        if len(response) == 0:
            return b''
        
        # Decode all hex data (must be even length for complete bytes)
        if len(response) % 2 != 0:
            raise RSPIOError(f"Unexpected response: odd number of hex digits")
        
        data_bytes = binascii.unhexlify(response)
        
        return data_bytes
    
    def _vfile_pwrite(self, fd: int, data: bytes) -> int:
        """Write to file via vFile:pwrite (sequential write, no offset)"""
        # Limit chunk size to fit in RSP packet
        # Packet format: "vFile:pwrite:<fd>,<hex-data>"
        # Reserve ~25 bytes for packet overhead (prefix + checksum)
        # Hex encoding doubles size, so max binary = (max_packet_size - 25) / 2
        max_binary = (self.max_packet_size - 25) // 2
        if len(data) > max_binary:
            data = data[:max_binary]
        
        # Encode data as hex (two hex digits per byte)
        hex_data = binascii.hexlify(data).decode('ascii')
        
        packet = f"vFile:pwrite:{fd:x},{hex_data}"
        response = self._send_packet_with_response(packet)
        
        if response.startswith("F-1,"):
            errno = self._parse_errno(response)
            self._raise_error(errno, "Failed to write file")
        
        # Parse F<count>
        if not response.startswith("F"):
            raise RSPIOError(f"Unexpected response: {response}")
        
        count_hex = response[1:]
        return int(count_hex, 16)
    
    def _vfile_size(self, path: str) -> int:
        """Get file size via vFile:size"""
        hex_path = self._encode_path(path)
        packet = f"vFile:size:{hex_path}"
        response = self._send_packet_with_response(packet)
        
        if response.startswith("F-1,"):
            errno = self._parse_errno(response)
            self._raise_error(errno, f"Failed to get size of {path}")
        
        # Parse F<size>
        if not response.startswith("F"):
            raise RSPIOError(f"Unexpected response: {response}")
        
        size_hex = response[1:]
        return int(size_hex, 16)
    
    def _vfile_exists(self, path: str) -> bool:
        """Check if file exists via vFile:exists"""
        hex_path = self._encode_path(path)
        packet = f"vFile:exists:{hex_path}"
        response = self._send_packet_with_response(packet)
        
        if response.startswith("F-1,"):
            errno = self._parse_errno(response)
            self._raise_error(errno, f"Failed to check existence of {path}")
        
        if response == "F,1":
            return True
        elif response == "F,0":
            return False
        else:
            raise RSPIOError(f"Unexpected response: {response}")
    
    def _vfile_unlink(self, path: str) -> None:
        """Delete file via vFile:unlink"""
        hex_path = self._encode_path(path)
        packet = f"vFile:unlink:{hex_path}"
        response = self._send_packet_with_response(packet)
        
        if response.startswith("F-1,"):
            errno = self._parse_errno(response)
            self._raise_error(errno, f"Failed to delete {path}")
        
        if response != "F0":
            raise RSPIOError(f"Unexpected response: {response}")
    
    # vSpectranext operations
    def _vspectranext_reboot(self) -> None:
        """Reboot device via vSpectranext:reboot"""
        response = self._send_packet_with_response("vSpectranext:reboot")
        if response != "OK":
            raise RSPIOError(f"Unexpected response: {response}")
    
    def _vspectranext_autoboot(self) -> None:
        """Configure autoboot and reboot via vSpectranext:autoboot"""
        response = self._send_packet_with_response("vSpectranext:autoboot")
        if response != "OK":
            raise RSPIOError(f"Unexpected response: {response}")
    
    def _vspectranext_opendir(self, path: str) -> None:
        """Open directory via vSpectranext:opendir"""
        hex_path = self._encode_path(path)
        packet = f"vSpectranext:opendir:{hex_path}"
        response = self._send_packet_with_response(packet)
        
        if response.startswith("E"):
            errno = self._parse_errno(response)
            self._raise_error(errno, f"Failed to open directory {path}")
        
        if response != "OK":
            raise RSPIOError(f"Unexpected response: {response}")
    
    def _vspectranext_readdir(self) -> Optional[Tuple[str, str, int]]:
        """Read directory entry via vSpectranext:readdir"""
        response = self._send_packet_with_response("vSpectranext:readdir")
        
        if response == "":
            return None  # End of directory
        
        if response.startswith("E"):
            errno = self._parse_errno(response)
            self._raise_error(errno, "Failed to read directory")
        
        # Parse OK,<hex-name>,<type>,<size>
        if not response.startswith("FOK,"):
            raise RSPIOError(f"Unexpected response: {response}")
        
        parts = response[4:].split(',')
        if len(parts) != 3:
            raise RSPIOError(f"Unexpected response format: {response}")
        
        hex_name, entry_type, size_hex = parts
        name = self._decode_path(hex_name)
        size = int(size_hex, 16)
        
        return (name, entry_type, size)
    
    def _vspectranext_closedir(self) -> None:
        """Close directory via vSpectranext:closedir"""
        response = self._send_packet_with_response("vSpectranext:closedir")
        
        if response.startswith("E"):
            errno = self._parse_errno(response)
            self._raise_error(errno, "Failed to close directory")
        
        if response != "OK":
            raise RSPIOError(f"Unexpected response: {response}")
    
    def _vspectranext_mv(self, old_path: str, new_path: str) -> None:
        """Move/rename file or directory via vSpectranext:mv"""
        old_hex = self._encode_path(old_path)
        new_hex = self._encode_path(new_path)
        packet = f"vSpectranext:mv:{old_hex},{new_hex}"
        response = self._send_packet_with_response(packet)
        
        if response.startswith("E"):
            errno = self._parse_errno(response)
            self._raise_error(errno, f"Failed to move {old_path} to {new_path}")
        
        if response != "OK":
            raise RSPIOError(f"Unexpected response: {response}")
    
    def _vspectranext_mkdir(self, path: str) -> None:
        """Create directory via vSpectranext:mkdir"""
        hex_path = self._encode_path(path)
        packet = f"vSpectranext:mkdir:{hex_path}"
        response = self._send_packet_with_response(packet)
        
        if response.startswith("E"):
            errno = self._parse_errno(response)
            self._raise_error(errno, f"Failed to create directory {path}")
        
        if response != "OK":
            raise RSPIOError(f"Unexpected response: {response}")
    
    def _vspectranext_rmdir(self, path: str) -> None:
        """Remove directory via vSpectranext:rmdir"""
        hex_path = self._encode_path(path)
        packet = f"vSpectranext:rmdir:{hex_path}"
        response = self._send_packet_with_response(packet)
        
        if response.startswith("E"):
            errno = self._parse_errno(response)
            self._raise_error(errno, f"Failed to remove directory {path}")
        
        if response != "OK":
            raise RSPIOError(f"Unexpected response: {response}")
    
    # High-level API
    def ls(self, path: str = "/") -> List[Tuple[str, str, int]]:
        """
        List directory contents.
        
        Args:
            path: Directory path (default: "/")
            
        Returns:
            List of tuples: (type, name, size) where type is 'D' or 'F'
        """
        self._vspectranext_opendir(path)
        entries = []
        try:
            while True:
                entry = self._vspectranext_readdir()
                if entry is None:
                    break
                name, entry_type, size = entry
                entries.append((entry_type, name, size))
        finally:
            self._vspectranext_closedir()
        
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
        
        sys.stdout.write(f"\r{operation}: [{bar}] {percent:.1f}% ({transferred_str}/{total_str})")
        sys.stdout.flush()
    
    def get(self, remote_path: str, local_path: str):
        """
        Download file from RAMFS.
        
        Args:
            remote_path: Path on device
            local_path: Local file path
        """
        # Get file size
        file_size = self._vfile_size(remote_path)
        
        if self.show_progress:
            print(f"Downloading {remote_path} -> {local_path} ({self._format_size(file_size)})")
        
        # Open file
        fd = self._vfile_open(remote_path, 0, 0)  # O_RDONLY
        
        try:
            transferred = 0
            start_time = time.time()
            
            with open(local_path, 'wb') as f:
                while transferred < file_size:
                    # Read chunk sequentially (limited by RSP packet size)
                    remaining = file_size - transferred
                    chunk_data = self._vfile_pread(fd, remaining)
                    if len(chunk_data) == 0:
                        break
                    
                    f.write(chunk_data)
                    transferred += len(chunk_data)
                    self._show_progress(transferred, file_size, "Downloading")
        finally:
            self._vfile_close(fd)
        
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
        
        if self.show_progress:
            print(f"Uploading {local_path} -> {remote_path} ({self._format_size(file_size)})")
        
        # Open file (O_WRONLY | O_CREAT | O_TRUNC)
        # O_WRONLY=1 (accmode), O_CREAT=0x0100, O_TRUNC=0x0200
        # Combined: 0x0201 (O_WRONLY=1 in accmode, O_TRUNC=0x0200 which also sets O_CREAT)
        fd = self._vfile_open(remote_path, 0x0201, 0)  # O_WRONLY | O_TRUNC (which includes O_CREAT)
        
        try:
            transferred = 0
            start_time = time.time()
            
            with open(local_path, 'rb') as f:
                while transferred < file_size:
                    # Read chunk from local file
                    # Limit to packet size: (max_packet_size - 25) / 2
                    max_chunk = (self.max_packet_size - 25) // 2
                    chunk = f.read(max_chunk)
                    if not chunk:
                        break
                    
                    # Write chunk sequentially (no offset)
                    bytes_written = self._vfile_pwrite(fd, chunk)
                    transferred += bytes_written
                    self._show_progress(transferred, file_size, "Uploading")
        finally:
            self._vfile_close(fd)
        
        if self.show_progress:
            elapsed = time.time() - start_time
            speed = transferred / elapsed if elapsed > 0 else 0
            print(f"\nUploaded {self._format_size(transferred)} in {elapsed:.1f}s ({self._format_size(speed)}/s)")
    
    def rm(self, path: str):
        """
        Delete file.
        
        Args:
            path: File path
        """
        self._vfile_unlink(path)
    
    def mv(self, old_path: str, new_path: str):
        """
        Move/rename file or directory.
        
        Args:
            old_path: Source path
            new_path: Destination path
        """
        self._vspectranext_mv(old_path, new_path)
    
    def mkdir(self, path: str):
        """
        Create directory.
        
        Args:
            path: Directory path
        """
        self._vspectranext_mkdir(path)
    
    def rmdir(self, path: str):
        """
        Remove directory.
        
        Args:
            path: Directory path
        """
        self._vspectranext_rmdir(path)
    
    def reboot(self):
        """Trigger ZX Spectrum reboot."""
        self._vspectranext_reboot()
    
    def autoboot(self):
        """Configure autoboot from xfs://ram/ and reboot ZX Spectrum."""
        self._vspectranext_autoboot()
    
    def set_o_packet_callback(self, callback):
        """Set callback for O-packets (log output)"""
        self._o_packet_callback = callback
    
    def execute_command(self, command: str, wait_for_response: bool = False, response_timeout: Optional[float] = None) -> Optional[str]:
        """
        Execute a CLI command via qRcmd packet.
        
        Args:
            command: Command string (e.g., "help", "wifi status")
            wait_for_response: If True, wait for OK/E response. If False, only wait for ACK.
            response_timeout: Timeout in seconds for waiting for response. If None, uses default (5.0) or infinite if wait_for_response=True and follow mode.
            
        Returns:
            Response code (OK, E01, E02, E03, E04) if wait_for_response=True, None otherwise
        """
        if not command or not command.strip():
            raise RSPInvalidError('Command cannot be empty')
        
        # Encode command as hex (same encoding as paths)
        hex_command = self._encode_path(command.strip())
        
        # Send qRcmd packet
        packet = f"qRcmd,{hex_command}"
        
        if wait_for_response:
            # Wait for OK/E response
            # Use provided timeout or default 5.0 seconds
            timeout = response_timeout if response_timeout is not None else 5.0
            response = self._send_packet_with_response(packet, timeout=timeout)

            # Handle response codes
            if response == 'OK':
                return 'OK'
            elif response.startswith('E'):
                error_code = response
                if error_code == 'E01':
                    raise RSPInvalidError('Invalid hex string in command')
                elif error_code == 'E02':
                    raise RSPInvalidError('Command too long')
                elif error_code == 'E03':
                    raise RSPInvalidError('Too many arguments')
                elif error_code == 'E04':
                    raise RSPInvalidError('Unknown command')
                else:
                    raise RSPIOError(f'Command error: {error_code}')
            
            return response
        else:
            # Just send packet and wait for ACK, don't wait for response
            self._send_packet(packet)
            return None
    
    def close(self):
        """Close connection"""
        # Stop reader thread
        if self._reader_thread is not None:
            self._reader_stop.set()
            # Reduce timeout so reader thread wakes up faster
            old_timeout = None
            if self.is_tcp:
                if self.sock:
                    try:
                        old_timeout = self.sock.gettimeout()
                        self.sock.settimeout(0.01)  # Very short timeout to wake up quickly
                    except:
                        pass  # Ignore errors when setting timeout
            else:
                if self.ser and self.ser.is_open:
                    try:
                        old_timeout = self.ser.timeout
                        self.ser.timeout = 0.01  # Very short timeout to wake up quickly
                    except:
                        pass  # Ignore errors when setting timeout (port may be closing)
            self._reader_thread.join(timeout=0.1)  # Reduced join timeout
            # Restore timeout if connection is still open
            if old_timeout is not None:
                if self.is_tcp:
                    if self.sock:
                        try:
                            self.sock.settimeout(old_timeout)
                        except:
                            pass
                else:
                    if self.ser and self.ser.is_open:
                        try:
                            self.ser.timeout = old_timeout
                        except:
                            pass  # Ignore errors when restoring timeout
            self._reader_thread = None
        
        # Close connection
        if self.is_tcp:
            if self.sock:
                try:
                    self.sock.close()
                except:
                    pass
                self.sock = None
        else:
            if self.ser and self.ser.is_open:
                self.ser.close()
        
        # Release lock
        if HAS_FCNTL and self._lock_fd is not None:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            except:
                pass  # Ignore errors when releasing lock
            try:
                os.close(self._lock_fd)
            except:
                pass  # Ignore errors when closing fd
            self._lock_fd = None
        elif HAS_MSVCRT and self._lock_fd is not None:
            try:
                msvcrt.locking(self._lock_fd, msvcrt.LK_UNLCK, 1)
            except:
                pass  # Ignore errors when releasing lock
            try:
                os.close(self._lock_fd)
            except:
                pass  # Ignore errors when closing fd
            try:
                if self._lock_file:
                    os.unlink(self._lock_file)
            except:
                pass  # Ignore errors when removing lock file
            self._lock_fd = None
            self._lock_file = None


# Command-line interface functions
def cmd_ls(args, show_progress: bool = True, verbose: bool = False):
    """List directory"""
    conn = SPXConnection(args.port, show_progress=show_progress, verbose=verbose)
    try:
        entries = conn.ls(args.path)
        for entry_type, name, size in entries:
            if entry_type == 'D':
                print(f"d {name:30s} {size:10d}")
            else:
                print(f"f {name:30s} {size:10d}")
    finally:
        conn.close()


def cmd_get(args, show_progress: bool = True, verbose: bool = False):
    """Download file"""
    conn = SPXConnection(args.port, show_progress=show_progress, verbose=verbose)
    try:
        conn.get(args.remote, args.local)
        if not show_progress:
            print(f"Downloaded {args.remote} -> {args.local}")
    finally:
        conn.close()


def cmd_put(args, show_progress: bool = True, verbose: bool = False):
    """Upload file"""
    conn = SPXConnection(args.port, show_progress=show_progress, verbose=verbose)
    try:
        conn.put(args.local, args.remote)
        if not show_progress:
            print(f"Uploaded {args.local} -> {args.remote}")
    finally:
        conn.close()


def cmd_rm(args, show_progress: bool = True, verbose: bool = False):
    """Delete file"""
    conn = SPXConnection(args.port, show_progress=show_progress, verbose=verbose)
    try:
        conn.rm(args.path)
        print(f"Deleted {args.path}")
    finally:
        conn.close()


def cmd_mv(args, show_progress: bool = True, verbose: bool = False):
    """Move/rename file"""
    conn = SPXConnection(args.port, show_progress=show_progress, verbose=verbose)
    try:
        conn.mv(args.old, args.new)
        print(f"Moved {args.old} -> {args.new}")
    finally:
        conn.close()


def cmd_mkdir(args, show_progress: bool = True, verbose: bool = False):
    """Create directory"""
    conn = SPXConnection(args.port, show_progress=show_progress, verbose=verbose)
    try:
        conn.mkdir(args.path)
        print(f"Created directory {args.path}")
    finally:
        conn.close()


def cmd_rmdir(args, show_progress: bool = True, verbose: bool = False):
    """Remove directory"""
    conn = SPXConnection(args.port, show_progress=show_progress, verbose=verbose)
    try:
        conn.rmdir(args.path)
        print(f"Removed directory {args.path}")
    finally:
        conn.close()


def cmd_reboot(args, show_progress: bool = True, verbose: bool = False):
    """Trigger ZX Spectrum reboot"""
    conn = SPXConnection(args.port, show_progress=show_progress, verbose=verbose)
    try:
        conn.reboot()
        print("Reboot command sent")
    finally:
        conn.close()


def cmd_autoboot(args, show_progress: bool = True, verbose: bool = False):
    """Configure autoboot from xfs://ram/ and reboot ZX Spectrum"""
    import signal
    import threading
    import time
    
    conn = SPXConnection(args.port, show_progress=show_progress, verbose=verbose)
    
    # Flag to track if we should continue streaming
    streaming = False
    should_stop = threading.Event()
    
    def o_packet_handler(log_msg: str):
        """Handle O-packets (log output)"""
        # Print without newline prefix, just the message
        print(log_msg, end='', flush=True)
    
    def signal_handler(signum, frame):
        """Handle Ctrl-C"""
        nonlocal streaming
        if streaming:
            print("\n[Interrupted]", file=sys.stderr)
            should_stop.set()
        else:
            sys.exit(1)
    
    # Set up signal handler for Ctrl-C
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Check if follow mode is enabled
        # When --follow is used without args, args.follow is True (const)
        # When --follow is used with a number, args.follow is that int
        follow_enabled = args.follow is not None
        # If args.follow is True (const), follow forever (no time limit)
        # If args.follow is an int, follow for that many seconds
        if args.follow is True:
            follow_seconds = None  # Follow forever
        elif isinstance(args.follow, int):
            follow_seconds = args.follow
        else:
            follow_seconds = None  # Shouldn't happen, but default to forever

        # Call autoboot
        conn.autoboot()
        
        if not follow_enabled:
            # Normal mode: just print success and exit
            print("Autoboot configured and reboot command sent")
        else:
            # Follow mode: stream output
            streaming = True
            if args.verbose:
                if follow_seconds is not None:
                    print(f"[Following terminal output for {follow_seconds} seconds]", file=sys.stderr)
                else:
                    print("[Following terminal output - Press Ctrl-C to stop]", file=sys.stderr)
            
            # Set O-packet callback to stream output
            conn.set_o_packet_callback(o_packet_handler)
            
            # Keep connection alive and stream O-packets
            try:
                start_time = time.time()
                while True:  # Loop forever until interrupted or time limit
                    # Check if we should stop (Ctrl-C)
                    if should_stop.is_set():
                        break
                    
                    # Check if we've exceeded the time limit (if specified)
                    if follow_seconds is not None:
                        elapsed = time.time() - start_time
                        if elapsed >= follow_seconds:
                            break
                    
                    # Sleep to avoid busy-waiting
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print("\n[Interrupted]", file=sys.stderr)
            finally:
                conn.set_o_packet_callback(None)
    finally:
        conn.close()


def cmd_exec(args, show_progress: bool = True, verbose: bool = False):
    """Execute a CLI command on the device"""
    import signal
    
    conn = SPXConnection(args.port, show_progress=show_progress, verbose=verbose)
    
    # Flag to track if we should continue streaming
    streaming = False
    should_stop = threading.Event()
    
    def o_packet_handler(log_msg: str):
        """Handle O-packets (log output)"""
        # Print without newline prefix, just the message
        print(log_msg, end='', flush=True)
    
    def signal_handler(signum, frame):
        """Handle Ctrl-C"""
        nonlocal streaming
        if streaming:
            print("\n[Interrupted]", file=sys.stderr)
            should_stop.set()
        else:
            sys.exit(1)
    
    # Set up signal handler for Ctrl-C
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Check if follow mode is enabled
        # When --follow is used without args, args.follow is True (const)
        # When --follow is used with a number, args.follow is that int
        follow_enabled = args.follow is not None
        # If args.follow is True (const), follow forever (no time limit)
        # If args.follow is an int, follow for that many seconds
        if args.follow is True:
            follow_seconds = None  # Follow forever
        elif isinstance(args.follow, int):
            follow_seconds = args.follow
        else:
            follow_seconds = None  # Shouldn't happen, but default to forever
        
        # Execute command
        # Only wait for response if follow mode is enabled
        # In follow mode, wait forever for OK response (O-packets may arrive first)
        response = conn.execute_command(args.cmd, wait_for_response=follow_enabled, 
                                       response_timeout=None if follow_enabled else None)
        
        if follow_enabled and response and response != 'OK':
            print(f"Error: {response}", file=sys.stderr)
            return

        if follow_enabled:
            # Follow mode: stream output
            streaming = True
            if args.verbose:
                if follow_seconds is not None:
                    print(f"[Executing: {args.cmd}]", file=sys.stderr)
                    print(f"[Following for {follow_seconds} seconds]", file=sys.stderr)
                else:
                    print(f"[Executing: {args.cmd}]", file=sys.stderr)
                    print("[Press Ctrl-C to stop]", file=sys.stderr)
            
            # Set O-packet callback to stream output
            conn.set_o_packet_callback(o_packet_handler)
            
            # Keep connection alive and stream O-packets
            try:
                start_time = time.time()
                while not should_stop.is_set():
                    # Check if we've exceeded the time limit (if specified)
                    if follow_seconds is not None:
                        elapsed = time.time() - start_time
                        if elapsed >= follow_seconds:
                            break
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print("\n[Interrupted]", file=sys.stderr)
            finally:
                conn.set_o_packet_callback(None)
        else:
            # Normal mode: exit immediately after ACK
            # O-packets that arrive after OK response won't be displayed
            pass
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='SPX - Spectranext tool')
    parser.add_argument('--port', '-p', help='Serial port (e.g., /dev/ttyACM0) or TCP address (e.g., localhost:1337). Auto-detect USB first, then fall back to localhost:1337 if not specified.')
    parser.add_argument('--no-progress', action='store_true', help='Disable progress indicators')
    parser.add_argument('--verbose', '-v', action='store_true', help='Log all data sent and received')
    
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
    
    # RM command
    parser_rm = subparsers.add_parser('rm', help='Delete file')
    parser_rm.add_argument('path', help='File path')
    
    # MV command
    parser_mv = subparsers.add_parser('mv', help='Move/rename file')
    parser_mv.add_argument('old', help='Old path')
    parser_mv.add_argument('new', help='New path')
    
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
    parser_autoboot.add_argument('--follow', '-f', nargs='?', type=int, const=True, metavar='SECONDS',
                                help='Stream terminal output continuously. If SECONDS is specified, follow for that many seconds then exit. If not specified, follow until Ctrl-C')
    
    # EXEC command
    parser_exec = subparsers.add_parser('exec', help='Execute a CLI command on the device')
    parser_exec.add_argument('cmd', metavar='command', help='Command to execute (e.g., "help", "wifi status")')
    parser_exec.add_argument('--follow', '-f', nargs='?', type=int, const=True, metavar='SECONDS',
                            help='Stream output continuously. If SECONDS is specified, follow for that many seconds then exit. If not specified, follow until Ctrl-C')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Create connection with progress setting
    show_progress = not args.no_progress
    verbose = args.verbose
    
    try:
        if args.command == 'ls':
            cmd_ls(args, show_progress, verbose)
        elif args.command == 'get':
            cmd_get(args, show_progress, verbose)
        elif args.command == 'put':
            cmd_put(args, show_progress, verbose)
        elif args.command == 'rm':
            cmd_rm(args, show_progress, verbose)
        elif args.command == 'mv':
            cmd_mv(args, show_progress, verbose)
        elif args.command == 'mkdir':
            cmd_mkdir(args, show_progress, verbose)
        elif args.command == 'rmdir':
            cmd_rmdir(args, show_progress, verbose)
        elif args.command == 'reboot':
            cmd_reboot(args, show_progress, verbose)
        elif args.command == 'autoboot':
            cmd_autoboot(args, show_progress, verbose)
        elif args.command == 'exec':
            cmd_exec(args, show_progress, verbose)
    except RSPNotFoundError as e:
        print(f"Error: Not found - {e}", file=sys.stderr)
        sys.exit(1)
    except RSPPermissionError as e:
        print(f"Error: Permission denied - {e}", file=sys.stderr)
        sys.exit(1)
    except RSPExistsError as e:
        print(f"Error: Already exists - {e}", file=sys.stderr)
        sys.exit(1)
    except RSPInvalidError as e:
        print(f"Error: Invalid - {e}", file=sys.stderr)
        sys.exit(1)
    except RSPIOError as e:
        print(f"Error: I/O error - {e}", file=sys.stderr)
        sys.exit(1)
    except RSPNotSupportedError as e:
        print(f"Error: Not supported - {e}", file=sys.stderr)
        sys.exit(1)
    except RSPException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
