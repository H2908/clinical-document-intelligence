"""Create a scanned-style PDF (image-only, no text layer) from a digital PDF.

Used to test the OCR fallback path. We take our existing patient_001
GP referral, render each page to a PNG at 200 DPI, then repackage those
PNGs as a new PDF with no embedded text. The result mimics what a real
scanner produces.
"""
from pathlib import Path
import fitz

SRC = Path("data/synthetic/documents/patient_001/01_GP_Referral_Thompson_12Jan2024.pdf")
OUT = Path("data/synthetic/documents/scanned_test.pdf")

src_doc = fitz.open(SRC)
out_doc = fitz.open()

dpi = 200  # realistic for a desktop scanner
zoom = dpi / 72
mat = fitz.Matrix(zoom, zoom)

for page in src_doc:
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img_bytes = pix.tobytes("png")
    rect = page.rect
    new_page = out_doc.new_page(width=rect.width, height=rect.height)
    new_page.insert_image(rect, stream=img_bytes)

out_doc.save(str(OUT))
out_doc.close()
src_doc.close()

print(f"Wrote scanned test PDF: {OUT}")
print(f"Size: {OUT.stat().st_size} bytes")

# Sanity check: does PyMuPDF find text in the new PDF?
check = fitz.open(OUT)
text = "\n".join(p.get_text() for p in check)
check.close()
print(f"PyMuPDF text extraction returns: {len(text.strip())} chars (should be 0 or near-0)")