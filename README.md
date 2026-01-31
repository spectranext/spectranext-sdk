# Spectranext SDK

SDK for developing applications for the [Spectranext cartridge](https://spectranext.net) (and for original Spectranet).

## Installation

### macOS / Linux

Run the installation script to set up z88dk and Python dependencies:

```bash
git clone https://github.com/spectranext/spectranext-sdk
cd spectranext-sdk
./install.sh
```

### Windows

**Option 1: Double-click installation (easiest)**

Simply double-click `install.bat` after cloning the repository:

```batch
git clone https://github.com/spectranext/spectranext-sdk
cd spectranext-sdk
# Double-click install.bat or run it from command prompt
install.bat
```

**Option 2: PowerShell script**

Run the PowerShell installation script directly:

```powershell
git clone https://github.com/spectranext/spectranext-sdk
cd spectranext-sdk
.\install.ps1
```

**Prerequisites for Windows:**
- Python 3.7 or later (download from https://www.python.org/downloads/)
  - Make sure to check "Add Python to PATH" during installation
- Git for Windows (download from https://git-scm.com/download/win)
- PowerShell 5.1 or later (included with Windows 10/11)

**Optional (for building zmakebas):**
- A C compiler (MinGW-w64, Visual Studio Build Tools, or MSYS2)
- Make utility (available in MSYS2 or via Chocolatey: `choco install make`)

The installation script will:
- Download and install z88dk toolchain
- Create a Python virtual environment
- Install required Python dependencies
- Build and install zmakebas (if a C compiler is available)

## Setup

### macOS / Linux

Source the SDK environment in your shell:

```bash
source spectranext-sdk/source.sh
```

Or add it to your shell configuration file (`~/.zshrc` or `~/.bashrc`):

```bash
source /path/to/spectranext-sdk/source.sh
```

### Windows

Source the SDK environment in PowerShell:

```powershell
. .\spectranext-sdk\source.ps1
```

Or add it to your PowerShell profile for automatic activation:

```powershell
Add-Content $PROFILE ". `"$PWD\spectranext-sdk\source.ps1`""
```

To find your PowerShell profile location:

```powershell
$PROFILE
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

# Set boot basic program (optional)
# This creates a boot.zx file that will be uploaded before your program
spectranext_set_boot("
10 %tapein \"idetest.tap\"
20 LOAD \"\"
")

# Add convenience targets (upload_bin, upload_tap, etc.)
spectranext_add_extra_outputs(idetest)
```

If `source.sh` is not sourced then `SPECTRANEXT_SDK_PATH` must be explicitly provided.

### Important Notes

- **`spectranext_sdk_init()` must be called before `project()`** - This is required because the SDK sets up the CMake toolchain, which must be configured before the project is defined.

### Boot BASIC Program

The `spectranext_set_boot()` function allows you to create a boot BASIC program that will be automatically uploaded before your main program. This is useful for creating loader programs or initialization code.

**Usage:**
```cmake
spectranext_set_boot("
10 PRINT \"Booting...\"
20 CLEAR 32767
30 %aload \"myprogram.bin\" CODE 32768
40 RANDOMIZE USR 32768
")
```

The function:
- Creates `boot.bas` in the CMake binary directory
- Compiles it to `boot.zx` using `zmakebas` (starting at line 10)
- Creates an `upload_boot` target that builds and uploads `boot.zx`
- When `spectranext_add_extra_outputs()` is called, `upload_bin` and `upload_tap` targets will automatically depend on `upload_boot` if it exists

**Example boot program:**
```cmake
spectranext_set_boot("
10 REM Boot loader
20 %tapein \"myprogram.tap\"
30 LOAD \"\"
40 REM Program will auto-run after loading
")
```

The boot program is compiled with `zmakebas -o boot.zx -a 10 boot.bas`, which means it starts at line 10. Make sure your BASIC code includes line numbers or uses labels if you're using zmakebas label mode.

### Available Targets

If `spectranext_set_boot()` was called, the following additional target is available:

- `upload_boot` - Build and upload `boot.zx` file for your BASIC loader program.

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
- `ZCCCFG` - z88dk configuration path
- `PATH` - Includes `z88dk/bin`

## SPX Tools

The SDK provides command-line tools for interacting with Spectranext:

### Spectranext filesystem tools

You can read on xfs tools a little bit more here: https://docs.spectranext.net/development/syncing-with-computer

- `spx-ls [path]` - List contents of RAMFS on Spectranext cartridge
- `spx-get <remote> <local>` - Download file from device
- `spx-put <local> <remote>` - Upload file to device
- `spx-mv <old> <new>` - Move/rename file
- `spx-rm <path>` - Delete file
- `spx-mkdir <path>` - Create directory
- `spx-rmdir <path>` - Remove directory
- `spx-reboot` - Trigger ZX Spectrum reboot
- `spx-autoboot` - Configure autoboot from xfs://ram/ and reboot
- `spx-terminal` - Show terminal connection info (macOS/Linux: launches minicom; Windows: shows connection settings)

Run `spx-help` for a list of available commands.

