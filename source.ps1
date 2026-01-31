# PowerShell script to set up Spectranext SDK environment
# Usage: . .\source.ps1

# Get the directory where this script is located
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path

# Verify the directory exists and contains source.ps1
if (-not (Test-Path "$SCRIPT_DIR\source.ps1")) {
    Write-Error "Error: source.ps1 not found in expected location: $SCRIPT_DIR"
    return
}

# Add to PATH
$env:PATH = "$SCRIPT_DIR\bin;$SCRIPT_DIR\z88dk\bin;$env:PATH"

# Set ZCCCFG environment variable
# Try to detect the actual location, fallback to standard path
$ZCCCFG_PATH = "$SCRIPT_DIR\z88dk\share\z88dk\lib\config"
if (-not (Test-Path $ZCCCFG_PATH)) {
    # Try alternative locations
    if (Test-Path "$SCRIPT_DIR\z88dk\lib\config") {
        $ZCCCFG_PATH = "$SCRIPT_DIR\z88dk\lib\config"
    } elseif (Test-Path "$SCRIPT_DIR\z88dk\config") {
        $ZCCCFG_PATH = "$SCRIPT_DIR\z88dk\config"
    } else {
        # Fallback to standard path
        $ZCCCFG_PATH = "$SCRIPT_DIR\z88dk\share\z88dk\lib\config"
    }
}
$env:ZCCCFG = $ZCCCFG_PATH

# Export CMake toolchain configuration for z88dk
$env:ZCCTARGET = "zx"
$ToolchainPath = "$SCRIPT_DIR\z88dk\support\cmake\Toolchain-zcc.cmake"
if (Test-Path $ToolchainPath) {
    $env:SPECTRANEXT_TOOLCHAIN = $ToolchainPath
}

# Export SDK include directory
$env:SPECTRANEXT_INCLUDE_DIR = "$SCRIPT_DIR\include"

# Export CMake SDK path
$env:SPECTRANEXT_SDK_PATH = $SCRIPT_DIR

# Source SPX helper script (skip in non-interactive environments like CLion)
# CLion executes .ps1 files but only needs environment variables, not interactive functions
$SPXScript = "$SCRIPT_DIR\bin\spx.ps1"
if (Test-Path $SPXScript) {
    # Detect if we're in a non-interactive environment (like CLion)
    # CLion runs PowerShell scripts but doesn't provide an interactive console
    $isInteractive = try {
        $null = $Host.UI.RawUI
        $Host.Name -ne "Default Host" -and $Host.Name -ne "ConsoleHost"
    } catch {
        $false
    }
    
    # Also check for CLION_ENV_MODE flag (can be set explicitly)
    $skipSPX = $env:CLION_ENV_MODE -or -not $isInteractive
    
    if (-not $skipSPX) {
        try {
            # Only source spx.ps1 in interactive shells
            . $SPXScript -ErrorAction SilentlyContinue 2>$null
        } catch {
            # Silently ignore - environment variables are what matter for CLion/CMake
        }
    }
    # In non-interactive mode (CLion), skip sourcing spx.ps1 entirely
    # The environment variables above are sufficient for CMake builds
}
