@echo off
REM AI Social Support Application - Windows Startup Script
REM =====================================================

echo.
echo ========================================
echo AI Social Support Application
echo Windows Local Runner
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.9+ from https://python.org
    pause
    exit /b 1
)

REM Check if we're in the right directory
if not exist "run_local.py" (
    echo ERROR: run_local.py not found
    echo Please run this script from the project root directory
    pause
    exit /b 1
)

REM Run the Python script with arguments
echo Starting AI Social Support Application...
echo.

python run_local.py %*

REM Check exit code
if errorlevel 1 (
    echo.
    echo ERROR: Application failed to start
    echo Check the error messages above
    pause
    exit /b 1
)

echo.
echo Application stopped.
pause