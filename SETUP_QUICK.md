# Quick Setup Guide - Windows

## Option 1: Batch Script (Recommended for simplicity)

If you encounter PowerShell errors, use the batch script instead:

```cmd
setup.bat
```

This will:
1. ✓ Check Python installation
2. ✓ Create virtual environment
3. ✓ Install all dependencies
4. ✓ Download scispacy model
5. ✓ Run verification

## Option 2: PowerShell Script

If you prefer PowerShell:

```powershell
.\setup-env.ps1
```

### If PowerShell script fails with syntax error:

The script uses Try/Catch for error handling. If you still get errors, use the batch script instead (Option 1).

## What Each Script Does

Both `setup.bat` and `setup-env.ps1` perform the same tasks:

1. **Verify Python** - Check Python 3.10+ is installed
2. **Create venv** - Create isolated Python environment
3. **Activate** - Activate the virtual environment
4. **Install deps** - pip install from requirements.txt
5. **Install scispacy model** - Download en_core_sci_md
6. **Verify** - Run verify_env.py to test everything

## Manual Installation (if scripts don't work)

If both scripts fail, you can install manually:

```bash
# 1. Create virtual environment
python -m venv venv

# 2. Activate it (Windows)
venv\Scripts\activate.bat

# 3. Install dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 4. Install scispacy model
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_md-0.5.4.tar.gz

# 5. Verify
python verify_env.py
```

## After Setup

### For next work sessions, activate venv:

**Command Prompt:**
```cmd
venv\Scripts\activate.bat
```

**PowerShell:**
```powershell
.\venv\Scripts\Activate.ps1
```

You'll see `(venv)` prefix in terminal when active.

### Install Tesseract (separate step)

Tesseract is a system-level dependency not installed via pip:

1. Download: https://github.com/UB-Mannheim/tesseract/wiki
2. Run the installer (accept defaults)
3. Optional: Update TESSERACT_PATH in .env if installed elsewhere

### Configure .env

Edit `.env` file with your credentials:

```
ANTHROPIC_API_KEY=your_key_here
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_DATABASE=your_database
SNOWFLAKE_WAREHOUSE=your_warehouse
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Python not found" | Install from https://python.org (must add to PATH) |
| "venv already exists" | Delete `venv` folder and try again |
| "Permission denied" | Run Command Prompt as Administrator |
| "pip install fails" | Check internet connection, try: `pip install --upgrade pip` |
| "scispacy model fails" | Non-critical - you can install it separately later |

## Success Indicators

After running setup, you should see:
- ✓ Virtual environment created
- ✓ All packages installed
- ✓ scispacy model available
- ✓ 17 sample PDFs verified
- ✓ PyMuPDF can read PDFs

Run `python verify_env.py` anytime to check status.
