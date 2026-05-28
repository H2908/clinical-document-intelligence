#!/usr/bin/env python3
"""
Environment setup verification script for Clinical Document Intelligence project.
Checks Python version, dependencies, Tesseract, and sample PDFs.
"""

import sys
import os
from pathlib import Path

def check_python_version():
    """Verify Python 3.10+"""
    version = sys.version_info
    status = "✓" if version.major >= 3 and version.minor >= 10 else "✗"
    print(f"{status} Python version: {version.major}.{version.minor}.{version.micro}")
    return version.major >= 3 and version.minor >= 10

def check_dependencies():
    """Verify critical dependencies are installed"""
    deps = [
        'fastapi', 'uvicorn', 'pymupdf', 'pytesseract', 'PIL',
        'spacy', 'anthropic', 'langgraph', 'pandas', 'pydantic',
        'boto3', 'snowflake'
    ]
    
    missing = []
    for dep in deps:
        try:
            if dep == 'PIL':
                import PIL
            elif dep == 'snowflake':
                import snowflake
            else:
                __import__(dep.replace('-', '_'))
            print(f"✓ {dep}")
        except ImportError:
            print(f"✗ {dep} - NOT INSTALLED")
            missing.append(dep)
    
    return len(missing) == 0

def check_scispacy():
    """Verify scispacy and model"""
    try:
        import scispacy
        print(f"✓ scispacy")
        
        # Try to load the model
        try:
            import spacy
            nlp = spacy.load("en_core_sci_md")
            print(f"✓ en_core_sci_md model loaded")
            return True
        except OSError:
            print(f"✗ en_core_sci_md model - NOT FOUND (run: pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_md-0.5.4.tar.gz)")
            return False
    except ImportError:
        print(f"✗ scispacy - NOT INSTALLED")
        return False

def check_tesseract():
    """Check if Tesseract is installed"""
    import shutil
    
    tesseract_path = shutil.which('tesseract')
    if tesseract_path:
        print(f"✓ Tesseract found at: {tesseract_path}")
        return True
    else:
        print(f"✗ Tesseract - NOT FOUND")
        print("  Windows: Download installer from https://github.com/UB-Mannheim/tesseract/wiki")
        print("  Mac: brew install tesseract")
        print("  Linux: apt-get install tesseract-ocr")
        return False

def check_sample_pdfs():
    """Verify sample PDFs are readable"""
    pdf_dir = Path(__file__).parent / "data" / "synthetic" / "nhs_data" / "pdfs"
    
    if not pdf_dir.exists():
        print(f"✗ PDF directory not found: {pdf_dir}")
        return False
    
    pdf_files = list(pdf_dir.glob("*.pdf"))
    print(f"✓ Found {len(pdf_files)} sample PDFs")
    
    if len(pdf_files) >= 17:
        print(f"✓ Required 17 PDFs present: {len(pdf_files)} files")
        
        # Try to read first PDF
        try:
            import fitz
            first_pdf = sorted(pdf_files)[0]
            doc = fitz.open(str(first_pdf))
            page_count = len(doc)
            print(f"✓ Successfully read {first_pdf.name}: {page_count} pages")
            return True
        except Exception as e:
            print(f"✗ Error reading PDF: {e}")
            return False
    else:
        print(f"✗ Only {len(pdf_files)} PDFs found (need 17)")
        return False

def main():
    """Run all checks"""
    print("\n=== Clinical Document Intelligence Environment Setup ===\n")
    
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("scispacy & Model", check_scispacy),
        ("Tesseract OCR", check_tesseract),
        ("Sample PDFs", check_sample_pdfs),
    ]
    
    results = {}
    for name, check_func in checks:
        print(f"\n{name}:")
        print("-" * 40)
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"✗ Error during check: {e}")
            results[name] = False
    
    print(f"\n{'=' * 50}")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"Summary: {passed}/{total} checks passed")
    
    if passed == total:
        print("✓ All checks passed! Environment is ready.")
        return 0
    else:
        print("✗ Some checks failed. See details above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
