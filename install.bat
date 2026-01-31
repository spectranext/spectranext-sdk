@echo off
REM Simple batch wrapper for PowerShell installation script
REM This allows users to double-click to install

echo Spectranext SDK Installer
echo ==========================
echo.

REM Check if PowerShell is available
where powershell >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Error: PowerShell is not available.
    echo Please install PowerShell or run install.ps1 manually.
    pause
    exit /b 1
)

REM Check execution policy and attempt to run script
echo Running installation script...
echo.

powershell.exe -ExecutionPolicy Bypass -File "%~dp0install.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Installation failed. See errors above.
    pause
    exit /b 1
)

echo.
echo Installation complete!
echo.
echo To activate the SDK environment, open PowerShell and run:
echo   . .\source.ps1
echo.
pause
