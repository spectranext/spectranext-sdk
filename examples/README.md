# Spectranext SDK Examples

This directory contains complete, working examples demonstrating how to use the Spectranext SDK.

## Examples

### https-example

Demonstrates how to make HTTPS requests using the `httplib` library. 
This example fetches data from `https://www.cloudflare.com/cdn-cgi/trace`.

**Features:**
- HTTPS/TLS support (automatic when using port 443)
- HTTP request/response handling
- Reading response headers and body

**See also:** [HTTPS Request Documentation](../../docs/docs/examples/https-request.md)

### file-io-example

Demonstrates how to read files using `libspdos` with XFS or TNFS filesystems.

**Features:**
- Standard C file operations (`fopen`, `fread`, `fclose`)
- Works with any mounted filesystem (XFS, TNFS)
- No pagination concerns

**See also:** [File I/O Documentation](../../docs/docs/examples/file-io.md)

## Uploading to Device

After building, upload to your Spectranext device:

```bash
cd https-example
cmake --build build --target https_example_tap_autoboot
```
