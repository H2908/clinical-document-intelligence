# ✅ Environment Setup Checklist

## Pre-Setup Verification
- [ ] Python 3.10+ installed
  ```powershell
  python --version
  ```
- [ ] Windows (or Mac/Linux equivalent)
- [ ] Internet connection (to download packages)

## Installation Steps

### 1. Run Automated Setup (Windows PowerShell)
- [ ] Open PowerShell in repository root
- [ ] Run: `.\setup-env.ps1`
- [ ] Wait for all steps to complete
- [ ] Verify no errors occurred

### 2. Install Tesseract (Manual)
- [ ] Download: https://github.com/UB-Mannheim/tesseract/wiki
- [ ] Run Windows installer
- [ ] Accept default path: `C:\Program Files\Tesseract-OCR`
- [ ] Update `.env` if installed elsewhere

### 3. Configure Environment
- [ ] Open `.env` in text editor
- [ ] Add `ANTHROPIC_API_KEY` (from claude.ai)
- [ ] Add `SNOWFLAKE_*` credentials (if using Snowflake)
- [ ] Add `AWS_*` credentials (if using S3)
- [ ] Save file (keep it secret!)

### 4. Verify Installation
- [ ] Run: `python verify_env.py`
- [ ] Check output for all ✓ marks
- [ ] Verify 17 sample PDFs loaded

## Post-Setup Tasks

### Before Each Work Session
- [ ] Activate virtual environment:
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
- [ ] Verify you see `(venv)` prefix in terminal

### Test Commands (Optional)
- [ ] Test PDF reading:
  ```bash
  python -c "import fitz; doc = fitz.open('data/synthetic/nhs_data/pdfs/GP_Referral_Hughes_p001.pdf'); print(f'✓ PDF: {len(doc)} pages')"
  ```

- [ ] Test scispacy:
  ```bash
  python -c "import scispacy; import spacy; nlp = spacy.load('en_core_sci_md'); print('✓ scispacy ready')"
  ```

- [ ] Test Anthropic SDK:
  ```bash
  python -c "from anthropic import Anthropic; print('✓ Anthropic SDK loaded')"
  ```

- [ ] Test FastAPI:
  ```bash
  python -c "from fastapi import FastAPI; print('✓ FastAPI ready')"
  ```

## Files Available to Reference
- `SETUP.md` - Detailed setup documentation
- `SETUP_SUMMARY.txt` - Quick overview
- `verify_env.py` - Automated verification
- `check_setup.py` - Quick status check
- `requirements.txt` - All dependencies listed
- `.env` - Configuration template

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `python not found` | Install Python 3.10+ from python.org |
| `venv\Scripts\Activate.ps1 not found` | Run `python -m venv venv` first |
| `en_core_sci_md model not found` | Run setup script or manual: `pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_md-0.5.4.tar.gz` |
| `tesseract not found` | Install from https://github.com/UB-Mannheim/tesseract/wiki |
| `PDF reading fails` | Verify PyMuPDF: `pip install pymupdf` |
| `Permission denied` | Run PowerShell as Admin or: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` |

## Success Criteria ✓

After setup is complete, you should have:

- [x] **17 Sample PDFs** in `data/synthetic/nhs_data/pdfs/`
- [x] **Python Dependencies** installed in `venv/`
- [x] **scispacy Model** available for import
- [x] **Tesseract** installed system-wide
- [x] **.env** configured with credentials
- [x] **verify_env.py** runs with all ✓ marks

When all items are complete, you're ready to develop!

## Quick Reference Commands

```powershell
# Activate venv
.\venv\Scripts\Activate.ps1

# Verify setup
python verify_env.py

# Check PDF directory
Get-ChildItem data\synthetic\nhs_data\pdfs\*.pdf | Measure-Object | Select-Object Count

# Update single package
pip install --upgrade fastapi

# Check package version
pip show anthropic
```

---

**Remember:** The `.env` file contains sensitive credentials. Never commit it to git!
