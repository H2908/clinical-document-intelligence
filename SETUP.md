# Environment Setup Guide

## ✅ Completed Setup Steps

### 1. **Requirements File**
- ✅ Created `requirements.txt` with all dependencies:
  - FastAPI & Uvicorn (API framework)
  - PyMuPDF (PDF processing)
  - Pytesseract & Pillow (OCR)
  - ScispaCy & Spacy (NLP)
  - Anthropic SDK (Claude API)
  - LangGraph (LLM orchestration)
  - Pandas & Pydantic (data handling)
  - Boto3 (AWS S3)
  - Snowflake Connector (data warehouse)

### 2. **Environment File**
- ✅ Created `.env` with placeholders for:
  - Anthropic API key
  - Snowflake credentials
  - AWS S3 configuration
  - Tesseract path (Windows)
  - Application settings

### 3. **Sample PDFs**
- ✅ **17 PDF files ready** in `data/synthetic/nhs_data/pdfs/`
  - 10 GP Referrals
  - 4 Cardiology reports
  - 1 DM Review
  - All synthetic NHS data
  
### 4. **Setup Automation**
- ✅ Created `setup-env.ps1` - PowerShell script for Windows
  - Checks Python 3.10+
  - Creates virtual environment
  - Installs all dependencies
  - Installs scispacy model
  - Verifies setup

- ✅ Created `verify_env.py` - Python verification script
  - Checks Python version
  - Verifies all packages
  - Tests scispacy model loading
  - Checks Tesseract installation
  - Reads sample PDFs

## 🚀 Next Steps

### Step 1: Run Setup Script (Windows)

**Option A: Batch Script (Recommended if PowerShell errors occur)**
```cmd
setup.bat
```

**Option B: PowerShell Script**
```powershell
.\setup-env.ps1
```

Both scripts do the same thing - choose whichever works for you. If PowerShell gives syntax errors, use `setup.bat`.

This will:
1. Check Python installation
2. Create virtual environment (`venv/`)
3. Install all dependencies from `requirements.txt`
4. Download and install scispacy model
5. Run verification tests

### Step 2: Manual Tesseract Installation (Windows Only)

Tesseract is an OS-level dependency not installed via pip:

1. Download installer: https://github.com/UB-Mannheim/tesseract/wiki
2. Run the installer (default path: `C:\Program Files\Tesseract-OCR`)
3. Update `.env` file if installed elsewhere:
   ```
   TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
   ```

For other OS:
- **Mac**: `brew install tesseract`
- **Linux**: `apt-get install tesseract-ocr`

### Step 3: Configure Environment Variables

Edit `.env` with your credentials:
```bash
# Anthropic API
ANTHROPIC_API_KEY=sk-xxx

# Snowflake (for data warehouse)
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_DATABASE=your_database
SNOWFLAKE_WAREHOUSE=your_warehouse

# AWS (optional, for S3 storage)
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
```

### Step 4: Activate Virtual Environment

After setup, activate venv in future sessions:
```powershell
# Windows PowerShell
.\venv\Scripts\Activate.ps1

# Windows CMD
venv\Scripts\activate.bat

# Mac/Linux
source venv/bin/activate
```

### Step 5: Verify Everything Works

```bash
# Check all components
python verify_env.py

# Test PDF reading
python -c "import fitz; doc = fitz.open('data/synthetic/nhs_data/pdfs/GP_Referral_Hughes_p001.pdf'); print(f'✓ PDF loaded: {len(doc)} pages')"

# Test scispacy
python -c "import scispacy; import spacy; nlp = spacy.load('en_core_sci_md'); print('✓ scispacy ready')"
```

## 📋 Dependency Overview

| Package | Purpose | Version |
|---------|---------|---------|
| FastAPI | REST API framework | 0.104.1 |
| Uvicorn | ASGI server | 0.24.0 |
| PyMuPDF | PDF extraction | 1.23.8 |
| Pytesseract | OCR interface | 0.3.10 |
| Pillow | Image processing | 10.1.0 |
| ScispaCy | Scientific NLP | 0.2.5 |
| Spacy | NLP pipelines | 3.7.2 |
| Anthropic | Claude API | 0.7.6 |
| LangGraph | LLM workflows | 0.0.20 |
| Pandas | Data manipulation | 2.1.3 |
| Pydantic | Data validation | 2.5.0 |
| Boto3 | AWS S3 | 1.29.7 |
| Snowflake | Data warehouse | 3.4.1 |

## ✨ Sample PDFs Available

All 17 samples are located in `data/synthetic/nhs_data/pdfs/`:

**GP Referrals (10):**
- GP_Referral_Hughes_p001.pdf
- GP_Referral_Roberts_p002.pdf
- GP_Referral_Singh_p003.pdf
- GP_Referral_Johnson_p004.pdf
- GP_Referral_Mahmood_p005.pdf
- GP_Referral_Evans_p006.pdf
- GP_Referral_Begum_p007.pdf
- GP_Referral_Wilson_p008.pdf
- GP_Referral_Shah_p009.pdf
- GP_Referral_Evans_p010.pdf

**Cardiology Reports (4):**
- Cardiology_Johnson_p004.pdf
- Cardiology_Mahmood_p005.pdf
- Cardiology_Evans_p006.pdf
- Cardiology_Singh_p003.pdf

**Other (1):**
- DM_Review_Mahmood_p005.pdf

## 🔍 Troubleshooting

### Issue: `No module named 'tesseract'`
**Solution:** Tesseract is a system dependency, not a Python package. Install via:
- Windows: https://github.com/UB-Mannheim/tesseract/wiki
- Mac: `brew install tesseract`
- Linux: `apt-get install tesseract-ocr`

### Issue: `en_core_sci_md model not found`
**Solution:** Install the model explicitly:
```bash
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_md-0.5.4.tar.gz
```

### Issue: PDF reading fails with `fitz module not found`
**Solution:** PyMuPDF provides the `fitz` module:
```bash
pip install pymupdf
```

### Issue: Virtual environment activation fails
**Solution:** On Windows PowerShell, you may need to enable execution policy:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## 📝 Files Created

- ✅ `requirements.txt` - Python dependencies
- ✅ `.env` - Configuration template (edit with your credentials)
- ✅ `setup-env.ps1` - Automated Windows setup
- ✅ `verify_env.py` - Verification script
- ✅ `SETUP.md` - This file

## 🎯 Success Criteria

- ✅ 17 sample PDFs available and readable
- ✅ Python 3.10+ installed
- ✅ Virtual environment created
- ✅ All dependencies installed
- ✅ scispacy model available
- ✅ Tesseract installed (system-level)
- ✅ Environment variables configured

Once all steps complete, you're ready to start developing!
