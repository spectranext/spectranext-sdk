@echo off
REM SPX wrapper for Windows - forwards arguments to spx.py
REM Usage: spx <command> [args...]

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"

REM Find Python command - prefer venv Python, fall back to system Python
set "PYTHON_CMD="

REM Try venv Python from ..\venv relative to script directory
set "VENV_DIR=%SCRIPT_DIR%..\venv"
if exist "%VENV_DIR%\bin\python3.exe" (
    set "PYTHON_CMD=%VENV_DIR%\bin\python3.exe"
) else if exist "%VENV_DIR%\Scripts\python3.exe" (
    set "PYTHON_CMD=%VENV_DIR%\Scripts\python3.exe"
) else if exist "%VENV_DIR%\bin\python.exe" (
    set "PYTHON_CMD=%VENV_DIR%\bin\python.exe"
) else if exist "%VENV_DIR%\Scripts\python.exe" (
    set "PYTHON_CMD=%VENV_DIR%\Scripts\python.exe"
)

REM Fallback to system Python
if "%PYTHON_CMD%"=="" (
    where python3 >nul 2>&1
    if %errorlevel% equ 0 (
        set "PYTHON_CMD=python3"
    ) else (
        where python >nul 2>&1
        if %errorlevel% equ 0 (
            set "PYTHON_CMD=python"
        )
    )
)

REM Verify Python works
if "%PYTHON_CMD%"=="" (
    echo Error: Python not found >&2
    exit /b 1
)

REM Forward all arguments to spx.py
"%PYTHON_CMD%" "%SCRIPT_DIR%spx.py" %*
