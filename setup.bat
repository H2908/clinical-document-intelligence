@echo off
REM Clinical Document Intelligence - Environment Setup (Windows CMD/Batch)
REM Run from Command Prompt or PowerShell: setup.bat

setlocal enabledelayedexpansion

cls
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║   Clinical Document Intelligence - Environment Setup        ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM Check Python version
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ✗ Python not found. Please install Python 3.10+
    echo   Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo ✓ Python found: %PYTHON_VERSION%
echo.

REM Create virtual environment
echo [2/5] Setting up virtual environment...
if exist venv (
    echo ✓ Virtual environment already exists
) else (
    echo Creating new virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ✗ Failed to create virtual environment
        pause
        exit /b 1
    )
    echo ✓ Virtual environment created
)
echo.

REM Activate virtual environment
echo [3/5] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ✗ Failed to activate virtual environment
    pause
    exit /b 1
)
echo ✓ Virtual environment activated
echo.

REM Upgrade pip
echo [4/5] Upgrading pip and installing dependencies...
python -m pip install --upgrade pip setuptools wheel >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
    echo ✗ Failed to install dependencies
    pause
    exit /b 1
)
echo ✓ Dependencies installed
echo.

REM Install scispacy model
echo [5/5] Installing scispacy language model...
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_md-0.5.4.tar.gz >nul 2>&1
if errorlevel 1 (
    echo ⚠ scispacy model installation may have had issues
    echo   You can install it manually with:
    echo   pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_md-0.5.4.tar.gz
) else (
    echo ✓ scispacy model installed
)
echo.

REM Run verification
echo ═══════════════════════════════════════════════════════════
echo Verifying environment setup...
echo ═══════════════════════════════════════════════════════════
echo.
python verify_env.py
echo.

echo ╔════════════════════════════════════════════════════════════╗
echo ║            Setup Complete - Ready to Develop!              ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo Virtual environment is active (see "(venv)" in prompt)
echo.
echo Next steps:
echo   1. Exit and re-open terminal, then run: venv\Scripts\activate.bat
echo   2. Install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
echo   3. Edit .env with your credentials
echo.
pause
