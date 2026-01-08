#!/usr/bin/env python3
"""
SPX Browser - Web interface for Spectranext RAMFS
"""

import sys
import os
import socket
import tempfile
import argparse
import webbrowser
import threading
import time
import signal
from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import serial.serialutil

# Import SPXConnection and exceptions from spx.py
# We need to add the parent directory to the path to import from spx
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from spx import (
    SPXConnection,
    USBFSException,
    USBFSNotFoundError,
    USBFSPermissionError,
    USBFSExistsError,
    USBFSIOError,
    find_free_port
)


def main():
    parser = argparse.ArgumentParser(description='SPX Browser - Web interface for Spectranext RAMFS')
    parser.add_argument('--port', type=int, help='Port to listen on (default: auto-detect)')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    args = parser.parse_args()
    
    # Get script directory to find browser static files
    browser_dir = os.path.join(script_dir, 'browser')
    
    if not os.path.exists(browser_dir):
        print(f"Error: Browser directory not found: {browser_dir}", file=sys.stderr)
        sys.exit(1)
    
    # Create FastAPI app
    app = FastAPI(title="SPX Browser", description="Web interface for Spectranext RAMFS")
    
    # Mount static files
    app.mount("/static", StaticFiles(directory=browser_dir), name="static")
    
    def get_connection():
        """Create a new SPX connection instance"""
        # Force auto-detection of USBFS port by passing None
        # This ensures we use the correct interface (interface 1 = USBFS)
        return SPXConnection(port=None, show_progress=False)
    
    @app.get("/")
    async def root():
        """Serve index.html"""
        return FileResponse(os.path.join(browser_dir, 'index.html'))
    
    @app.get("/download/{path:path}")
    async def download_file(path: str):
        """Download file from RAMFS"""
        # Normalize path
        if not path:
            raise HTTPException(status_code=400, detail="Path cannot be empty")
        ramfs_path = "/" + path.lstrip("/").replace("//", "/")
        
        tmp_path = None
        conn = get_connection()
        try:
            # Create temporary file to store downloaded content
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_path = tmp_file.name
            
            # Try to download the file
            conn.get(ramfs_path, tmp_path)
            
            # Get filename from path
            filename = os.path.basename(path) or "file"
            
            response = FileResponse(
                tmp_path,
                media_type='application/octet-stream',
                filename=filename
            )
            return response
        except USBFSNotFoundError as e:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            error_msg = str(e) if str(e) else f"File not found: {ramfs_path}"
            raise HTTPException(status_code=404, detail=error_msg)
        except (serial.serialutil.SerialException, OSError) as e:
            # USB device disconnected or error
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise HTTPException(status_code=503, detail=f"Device connection error: {str(e)}")
        except USBFSException as e:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            # Close connection after use
            conn.close()
      
    
    @app.get("/ramfs/{path:path}")
    async def list_directory(path: str):
        """List directory contents"""
        # Normalize path
        if path == "" or path == "/":
            ramfs_path = "/"
        else:
            ramfs_path = "/" + path.lstrip("/").replace("//", "/")
        
        conn = get_connection()
        try:
            entries = conn.ls(ramfs_path)
            result = {
                "entries": [
                    {
                        "type": "folder" if entry_type == "D" else "file",
                        "name": name,
                        "size": size
                    }
                    for entry_type, name, size in entries
                ]
            }
            return JSONResponse(content=result)
        except USBFSNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except (serial.serialutil.SerialException, OSError) as e:
            # USB device disconnected or error
            raise HTTPException(status_code=503, detail=f"Device connection error: {str(e)}")
        except USBFSException as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            # Close connection after use
            conn.close()
    
    @app.post("/ramfs/{path:path}")
    async def upload_file(path: str, file: UploadFile = File(...)):
        """Upload file to RAMFS"""
        tmp_path = None
        try:
            # Normalize path - path should include the filename
            # If path is empty or just "/", use the uploaded filename
            if not path or path == "/":
                # Get filename from the uploaded file
                filename = file.filename
                if not filename:
                    raise HTTPException(status_code=400, detail="Path cannot be empty and filename not provided")
                ramfs_path = "/" + filename
            else:
                ramfs_path = "/" + path.lstrip("/").replace("//", "/")
            
            # Create temporary file to store uploaded content
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_path = tmp_file.name
                # Write uploaded content to temp file
                content = await file.read()
                if not content:
                    raise HTTPException(status_code=400, detail="File is empty")
                tmp_file.write(content)
            
            conn = get_connection()
            try:
                conn.put(tmp_path, ramfs_path)
                return JSONResponse(content={"message": "File uploaded successfully"})
            finally:
                # Close connection after use
                conn.close()
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
        except USBFSExistsError as e:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise HTTPException(status_code=409, detail=str(e))
        except (serial.serialutil.SerialException, OSError) as e:
            # USB device disconnected or error
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise HTTPException(status_code=503, detail=f"Device connection error: {str(e)}")
        except USBFSException as e:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            # Catch any other exceptions
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
    @app.delete("/ramfs/{path:path}")
    async def delete_item(path: str):
        """Delete file or directory from RAMFS"""
        try:
            ramfs_path = "/" + path.lstrip("/")
            
            conn = get_connection()
            try:
                # Try to delete as file first, then as directory if not found
                try:
                    conn.rm(ramfs_path)
                    return JSONResponse(content={"message": "File deleted successfully"})
                except USBFSNotFoundError:
                    # Not a file, try as directory
                    conn.rmdir(ramfs_path)
                    return JSONResponse(content={"message": "Directory deleted successfully"})
            finally:
                # Close connection after use
                conn.close()
        except USBFSNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except USBFSPermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except (serial.serialutil.SerialException, OSError) as e:
            # USB device disconnected or error
            raise HTTPException(status_code=503, detail=f"Device connection error: {str(e)}")
        except USBFSException as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/mkdir/{path:path}")
    async def create_directory(path: str):
        """Create directory in RAMFS"""
        try:
            ramfs_path = "/" + path.lstrip("/")
            
            conn = get_connection()
            try:
                conn.mkdir(ramfs_path)
                return JSONResponse(content={"message": "Directory created successfully"})
            finally:
                # Close connection after use
                conn.close()
        except USBFSExistsError as e:
            raise HTTPException(status_code=409, detail=str(e))
        except (serial.serialutil.SerialException, OSError) as e:
            # USB device disconnected or error
            raise HTTPException(status_code=503, detail=f"Device connection error: {str(e)}")
        except USBFSException as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # Determine port
    if args.port:
        port = args.port
    else:
        port = find_free_port(8000)
    
    url = f"http://{args.host}:{port}"
    print(f"Starting SPX Browser on {url}")
    print("Press Ctrl+C to stop")
    
    # Open browser after a short delay to ensure server is ready
    def open_browser():
        time.sleep(1)  # Wait for server to start
        webbrowser.open(url)
    
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    uvicorn.run(app, host=args.host, port=port)


if __name__ == "__main__":
    main()

