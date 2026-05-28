@echo off
REM Quick reference for setup commands on Windows

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║   Clinical Document Intelligence - Quick Commands           ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo SETUP (first time only):
echo   setup.bat
echo.
echo Or use PowerShell:
echo   .\setup-env.ps1
echo.
echo ─────────────────────────────────────────────────────────────
echo.
echo AFTER SETUP - Activate virtual environment:
echo   venv\Scripts\activate.bat
echo.
echo VERIFY ENVIRONMENT:
echo   python verify_env.py
echo.
echo TEST PDF READING:
echo   python -c "import fitz; doc = fitz.open('data/synthetic/nhs_data/pdfs/GP_Referral_Hughes_p001.pdf'); print(f'Loaded: {len(doc)} pages')"
echo.
echo TEST SCISPACY:
echo   python -c "import spacy; nlp = spacy.load('en_core_sci_md'); print('Ready!')"
echo.
echo ─────────────────────────────────────────────────────────────
echo.
echo For details, see: SETUP.md or SETUP_QUICK.md
echo.
pause
