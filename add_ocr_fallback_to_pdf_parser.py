"""Wrap parse_pdf with an OCR fallback for scanned PDFs.

When parse_pdf raises ValueError with 'No extractable text' (the existing
scan-detection signal), call ocr_engine.ocr_pdf and return its output
instead. All other ValueErrors (encrypted, malformed, not-a-PDF) re-raise
unchanged — OCR doesn't help with those.

Atomic: aborts if the anchor isn't found or if the OCR import is already
present (idempotent).
"""
from pathlib import Path

p = Path("parsers/pdf_parser.py")
src = p.read_text(encoding="utf-8")

if "from parsers.ocr_engine import" in src or "_ocr_fallback" in src:
    print("[SKIP] OCR fallback already wired into parse_pdf - nothing to do")
    raise SystemExit(0)

# Anchor: the final line of the existing parse_pdf function body
old = '''    text = "\\n".join(pages)
    if not text.strip():
        raise ValueError(
            f"No extractable text in {path}. "
            "If this is a scanned PDF, OCR is needed (Phase 4, L2)."
        )
    return text'''

new = '''    text = "\\n".join(pages)
    if not text.strip():
        # Phase 4 L2: fall back to OCR for scanned PDFs.
        # Import lazily so users without Tesseract installed only hit the
        # import error when they actually need OCR.
        from parsers.ocr_engine import ocr_pdf as _ocr_fallback
        import logging
        logging.getLogger(__name__).info(
            f"No extractable text in {path} - falling back to OCR (Tesseract)"
        )
        return _ocr_fallback(path)
    return text'''

if old not in src:
    print("[FAIL] anchor not found in parsers/pdf_parser.py - aborting")
    raise SystemExit(1)
if src.count(old) > 1:
    print(f"[FAIL] anchor matched {src.count(old)} times - aborting")
    raise SystemExit(1)

new_src = src.replace(old, new)
p.write_text(new_src, encoding="utf-8", newline="\n")
print(f"Wrapped parse_pdf with OCR fallback")
print(f"File now {len(new_src.splitlines())} lines")