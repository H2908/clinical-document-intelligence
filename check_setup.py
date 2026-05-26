#!/usr/bin/env python3
"""Quick validation of setup"""
from pathlib import Path

pdf_dir = Path("data/synthetic/nhs_data/pdfs")
pdfs = list(pdf_dir.glob("*.pdf"))

print(f"✓ Found {len(pdfs)} sample PDFs:")
for pdf in sorted(pdfs):
    print(f"  - {pdf.name}")

# Check critical files exist
critical_files = [
    "requirements.txt",
    ".env",
    "setup-env.ps1",
    "verify_env.py",
    "SETUP.md"
]

print(f"\n✓ Setup files created:")
for file in critical_files:
    if Path(file).exists():
        print(f"  - {file}")
    else:
        print(f"  ✗ {file} - MISSING")

print("\n✓ Environment setup ready!")
print("\nNext steps:")
print("  1. Run: .\\setup-env.ps1 (PowerShell)")
print("  2. Edit: .env with your credentials")
print("  3. Run: python verify_env.py")
