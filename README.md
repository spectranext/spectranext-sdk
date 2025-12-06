# Spectranext SDK

SDK for developing applications for the [Spectranext cartridge](https://spectranext.net) (and for original Spectranet).

## Installation

Run the installation script to set up z88dk and Python dependencies:

```bash
git clone https://github.com/spectranext/spectranext-sdk
cd spectranext-sdk
./install.sh
```

This will:
- Download and install z88dk toolchain
- Create a Python virtual environment
- Install required Python dependencies

## Setup

Source the SDK environment in your shell:

```bash
source spectranext-sdk/source.sh
```

Or add it to your shell configuration file (`~/.zshrc` or `~/.bashrc`):

```bash
source /path/to/spectranext-sdk/source.sh
```

## Setting Up a CMake Project

Create a `CMakeLists.txt` file in your project directory:

```cmake
cmake_minimum_required(VERSION 3.16)

# Import Spectranext SDK - MUST be before project()
include($ENV{SPECTRANEXT_SDK_PATH}/cmake/spectranext_sdk_import.cmake)
spectranext_sdk_init()

project(idetest C)

add_executable(idetest main.c)

target_compile_options(idetest PUBLIC -debug)

target_link_libraries(idetest PUBLIC -lndos -llibspectranet.lib -llibsocket.lib)

target_link_options(idetest PUBLIC -debug -create-app)

# Add convenience targets (upload_bin, upload_tap, etc.)
spectranext_add_extra_outputs(idetest)
```

If `source.sh` is not sourced then `SPECTRANEXT_SDK_PATH` must be explicitly provided.

### Important Notes

- **`spectranext_sdk_init()` must be called before `project()`** - This is required because the SDK sets up the CMake toolchain, which must be configured before the project is defined.

### Available Targets

After calling `spectranext_add_extra_outputs(project_name)`, the following targets are available:

- `project_name_upload_bin` - Build and upload `.bin` file
- `project_name_upload_tap` - Build and upload `.tap` file
- `project_name_bin_autoboot` - Build, upload `.bin`, and configure autoboot
- `project_name_tap_autoboot` - Build, upload `.tap`, and configure autoboot

### Building and Uploading

```bash
# Configure CMake (if not already done)
cmake -B build

# Build and upload .bin file
cmake --build build --target idetest_upload_bin

# Build and upload .tap file
cmake --build build --target idetest_upload_tap

# Build, upload, and configure autoboot
cmake --build build --target idetest_bin_autoboot
```

## SDK Components

- **z88dk** - Z80 cross-compiler toolchain
- **SPX Tools** - Command-line tools for interacting with Spectranext (`spx-ls`, `spx-get`, `spx-put`, etc.)
- **CMake Integration** - Automatic toolchain setup and convenience targets
- **Headers** - Spectranext API headers in `include/`
- **Libraries** - Pre-built libraries in `clibs/`

## Environment Variables

The SDK sets the following environment variables:

- `SPECTRANEXT_SDK_PATH` - Path to the SDK root directory
- `SPECTRANEXT_TOOLCHAIN` - Path to the CMake toolchain file
- `SPECTRANEXT_INCLUDE_DIR` - Path to SDK include directory
- `ZCCTARGET` - z88dk target (default: `zx`)
- `SPX_SDK_DIR` - SDK directory for SPX tools
- `ZCCCFG` - z88dk configuration path
- `PATH` - Includes `z88dk/bin`

## SPX Tools

The SDK provides command-line tools for interacting with Spectranext:

### Spectranext filesystem tools

You can read on xfs tools a little bit more here: https://docs.spectranext.net/development/xfs

- `spx-ls [path]` - List contents of RAMFS on Spectranext cartridge
- `spx-get <remote> <local>` - Download file from device
- `spx-put <local> <remote>` - Upload file to device
- `spx-mv <old> <new>` - Move/rename file
- `spx-rm <path>` - Delete file
- `spx-mkdir <path>` - Create directory
- `spx-rmdir <path>` - Remove directory
- `spx-reboot` - Trigger ZX Spectrum reboot
- `spx-autoboot` - Configure autoboot from xfs://ram/ and reboot
- `spx-terminal` - Launch minicom terminal on console port

Run `spx-help` for a list of available commands.

