# Clinical Document Intelligence - Environment Setup Script
# Run in PowerShell: .\setup-env.ps1
# If you get an error, use: setup.bat instead

Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Clinical Document Intelligence - Environment Setup        ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan

# Check Python version
Write-Host "`n[1/5] Checking Python installation..." -ForegroundColor Yellow
Try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} Catch {
    Write-Host "✗ Python not found. Please install Python 3.10+" -ForegroundColor Red
    Write-Host "  Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# Create virtual environment
Write-Host "`n[2/5] Setting up virtual environment..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "✓ Virtual environment already exists" -ForegroundColor Green
} else {
    Write-Host "Creating new virtual environment..." -ForegroundColor Cyan
    python -m venv venv
    Write-Host "✓ Virtual environment created" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "`n[3/5] Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1
Write-Host "✓ Virtual environment activated" -ForegroundColor Green

# Install dependencies
Write-Host "`n[4/5] Installing Python dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Dependencies installed" -ForegroundColor Green
} else {
    Write-Host "✗ Failed to install dependencies" -ForegroundColor Red
    exit 1
}

# Install scispacy model
Write-Host "`n[5/5] Installing scispacy language model..." -ForegroundColor Yellow
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_md-0.5.4.tar.gz
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ scispacy model installed" -ForegroundColor Green
} else {
    Write-Host "⚠ scispacy model installation had issues (non-critical)" -ForegroundColor Yellow
}

# Verify environment
Write-Host "`n═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "Verifying environment setup..." -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
python verify_env.py
Write-Host ""

Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║            Setup Complete - Ready to Develop!              ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "Virtual environment is now active (see '(venv)' in prompt)" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki" -ForegroundColor White
Write-Host "  2. Edit .env with your credentials (ANTHROPIC_API_KEY, etc.)" -ForegroundColor White
Write-Host "  3. Verify with: python verify_env.py" -ForegroundColor White
Write-Host ""

