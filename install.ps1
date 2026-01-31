# PowerShell installation script for Spectranext SDK on Windows
# Requires PowerShell 5.1 or later

$ErrorActionPreference = "Stop"

# z88dk version to install
$Z88DK_VERSION = "2.3"

# Get the directory where this script is located
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $SCRIPT_DIR

Write-Host "Detected OS: Windows" -ForegroundColor Green

# Check if z88dk already exists (idempotent)
if ((Test-Path "z88dk") -and (Test-Path "z88dk\bin\zcc.exe")) {
    Write-Host "z88dk already installed, skipping..." -ForegroundColor Yellow
} else {
    Write-Host "Installing z88dk for Windows..." -ForegroundColor Green
    
    # Determine if we're on 64-bit or 32-bit Windows
    $Is64Bit = [Environment]::Is64BitOperatingSystem
    
    # Download z88dk binary release
    if ($Is64Bit) {
        $Z88DK_URL = "https://github.com/z88dk/z88dk/releases/download/v${Z88DK_VERSION}/z88dk-win32-${Z88DK_VERSION}.zip"
        $Z88DK_ZIP = "z88dk-win32-${Z88DK_VERSION}.zip"
    } else {
        # For 32-bit, try the same zip (it may contain both)
        $Z88DK_URL = "https://github.com/z88dk/z88dk/releases/download/v${Z88DK_VERSION}/z88dk-win32-${Z88DK_VERSION}.zip"
        $Z88DK_ZIP = "z88dk-win32-${Z88DK_VERSION}.zip"
    }
    
    if (-not (Test-Path $Z88DK_ZIP)) {
        Write-Host "Downloading z88dk..." -ForegroundColor Green
        try {
            Invoke-WebRequest -Uri $Z88DK_URL -OutFile $Z88DK_ZIP -UseBasicParsing
        } catch {
            Write-Host "Error downloading z88dk. Trying alternative URL..." -ForegroundColor Yellow
            # Try nightly build as fallback
            $Z88DK_URL = "http://nightly.z88dk.org/z88dk-win32-latest.zip"
            Invoke-WebRequest -Uri $Z88DK_URL -OutFile $Z88DK_ZIP -UseBasicParsing
        }
    }
    
    # Extract to z88dk folder
    Write-Host "Extracting z88dk..." -ForegroundColor Green
    Expand-Archive -Path $Z88DK_ZIP -DestinationPath "." -Force
    
    # The zip might extract to a subdirectory, move contents if needed
    $ExtractedDir = Get-ChildItem -Directory | Where-Object { $_.Name -like "z88dk*" -and $_.Name -ne "z88dk" } | Select-Object -First 1
    if ($ExtractedDir) {
        if (Test-Path "z88dk") {
            Remove-Item "z88dk" -Recurse -Force
        }
        Rename-Item $ExtractedDir.FullName "z88dk"
    }
    
    # Clean up zip file
    Remove-Item $Z88DK_ZIP -Force -ErrorAction SilentlyContinue
    
    Write-Host "z88dk installation complete!" -ForegroundColor Green
}

# Check if Python is installed
$PythonCmd = $null
$PythonPaths = @("python3", "python", "py")
foreach ($py in $PythonPaths) {
    try {
        $result = & $py --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $PythonCmd = $py
            Write-Host "Found Python: $py" -ForegroundColor Green
            break
        }
    } catch {
        continue
    }
}

if (-not $PythonCmd) {
    Write-Host "Error: Python not found. Please install Python 3.7 or later from https://www.python.org/downloads/" -ForegroundColor Red
    Write-Host "Make sure to check 'Add Python to PATH' during installation." -ForegroundColor Yellow
    exit 1
}

# Create Python venv if it doesn't exist (idempotent)
if (-not (Test-Path "venv")) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Green
    & $PythonCmd -m venv venv
    Write-Host "Virtual environment created!" -ForegroundColor Green
} else {
    Write-Host "Virtual environment already exists, skipping creation..." -ForegroundColor Yellow
}

# Install/upgrade Python dependencies
if (Test-Path "requirements.txt") {
    Write-Host "Installing Python dependencies..." -ForegroundColor Green
    $VenvPython = Join-Path $SCRIPT_DIR "venv\Scripts\python.exe"
    
    if (Test-Path $VenvPython) {
        # Use venv Python directly
        Write-Host "Using venv Python: $VenvPython" -ForegroundColor Cyan
        & $VenvPython -m pip install --upgrade pip
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Warning: pip upgrade failed, continuing anyway..." -ForegroundColor Yellow
        }
        
        Write-Host "Installing packages from requirements.txt..." -ForegroundColor Cyan
        & $VenvPython -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error: Failed to install dependencies from requirements.txt" -ForegroundColor Red
            exit 1
        }
        
        # Verify critical package is installed
        Write-Host "Verifying installation..." -ForegroundColor Cyan
        $checkResult = & $VenvPython -c "import serial; print('pyserial OK')" 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error: pyserial verification failed!" -ForegroundColor Red
            Write-Host "Output: $checkResult" -ForegroundColor Red
            exit 1
        }
        Write-Host "Verified: pyserial is installed" -ForegroundColor Green
    } else {
        # Fallback to system Python
        Write-Host "Warning: venv Python not found, using system Python: $PythonCmd" -ForegroundColor Yellow
        & $PythonCmd -m pip install --upgrade pip
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Warning: pip upgrade failed, continuing anyway..." -ForegroundColor Yellow
        }
        
        Write-Host "Installing packages from requirements.txt..." -ForegroundColor Cyan
        & $PythonCmd -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error: Failed to install dependencies from requirements.txt" -ForegroundColor Red
            exit 1
        }
    }
    
    Write-Host "Python dependencies installed!" -ForegroundColor Green
} else {
    Write-Host "Warning: requirements.txt not found, skipping dependency installation" -ForegroundColor Yellow
}

# Verify pymakebas.py exists (it should be in the repository)
if (-not (Test-Path "bin\pymakebas.py")) {
    Write-Host "Warning: bin\pymakebas.py not found. Make sure it's in the repository." -ForegroundColor Yellow
} else {
    Write-Host "pymakebas.py found - zmakebas functionality available via Python wrapper" -ForegroundColor Green
}

Write-Host ""
Write-Host "Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To use the SDK tools, add the bin folder to your PATH:" -ForegroundColor Cyan
Write-Host ""
$binPath = "$SCRIPT_DIR\bin"
Write-Host "  [Environment]::SetEnvironmentVariable('Path', [Environment]::GetEnvironmentVariable('Path', 'User') + ';$binPath', 'User')" -ForegroundColor White
Write-Host ""
Write-Host "Or manually add this folder to your PATH environment variable:" -ForegroundColor Cyan
Write-Host "  $binPath" -ForegroundColor White
Write-Host ""
Write-Host "To activate the SDK environment in the current PowerShell session, run:" -ForegroundColor Cyan
Write-Host ('  . "' + $SCRIPT_DIR + '\source.ps1"') -ForegroundColor White
Write-Host ""
