"""OCR engine — Tesseract local + Textract opt-in fallback.

Phase 4 / L2. Used by parsers.pdf_parser as a fallback path when PyMuPDF
returns no extractable text (scanned PDFs).

Tesseract is the default. Textract is opt-in via the use_textract=True
arg — chosen for cost reasons (Textract bills per page; Tesseract is free).

Rendering: PyMuPDF rasterises each PDF page to a Pillow image at 300 DPI,
which is the standard OCR resolution. Higher DPIs improve accuracy on
small fonts but cost time and memory.
"""
from __future__ import annotations
from pathlib import Path
from io import BytesIO
import logging
import os

import fitz  # PyMuPDF
from PIL import Image
import pytesseract

log = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# Tesseract binary location
# ----------------------------------------------------------------------------
# On Windows the binary is installed outside PATH by default. Point pytesseract
# at it explicitly. On Linux/Mac the binary is on PATH and this is a no-op.

_TESSERACT_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


def _resolve_tesseract_path() -> str | None:
    """Locate the tesseract binary on Windows. Returns None on non-Windows."""
    if os.name != "nt":
        return None
    for candidate in _TESSERACT_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return None


_tess_path = _resolve_tesseract_path()
if _tess_path:
    pytesseract.pytesseract.tesseract_cmd = _tess_path


# ----------------------------------------------------------------------------
# Page rendering
# ----------------------------------------------------------------------------

def _render_page_to_image(page: fitz.Page, dpi: int = 300) -> Image.Image:
    """Rasterise a single PDF page to a PIL Image at the given DPI."""
    zoom = dpi / 72  # PyMuPDF default is 72 DPI
    matrix = fitz.Matrix(zoom, zoom)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    img_bytes = pixmap.tobytes("png")
    return Image.open(BytesIO(img_bytes))


# ----------------------------------------------------------------------------
# Tesseract OCR
# ----------------------------------------------------------------------------

def ocr_pdf_tesseract(file_path: str | Path, dpi: int = 300) -> str:
    """Run Tesseract OCR on every page of a PDF, return concatenated text.

    Args:
        file_path: path to the PDF.
        dpi: render DPI (default 300, standard for OCR).

    Returns:
        Plain text, pages joined with single newlines.

    Raises:
        FileNotFoundError: if path doesn't exist.
        ValueError: if PDF can't be opened or OCR returns nothing.
        RuntimeError: if Tesseract binary not found.
    """
    if _tess_path is None and os.name == "nt":
        raise RuntimeError(
            "Tesseract binary not found in any of: "
            + ", ".join(_TESSERACT_CANDIDATES)
            + ". Install from https://github.com/UB-Mannheim/tesseract/wiki"
        )

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    try:
        doc = fitz.open(path)
    except Exception as e:
        raise ValueError(f"Could not open PDF for OCR {path}: {e}") from e

    pages_text = []
    try:
        for page_num, page in enumerate(doc):
            img = _render_page_to_image(page, dpi=dpi)
            page_text = pytesseract.image_to_string(img)
            pages_text.append(page_text)
            log.info(f"OCR page {page_num + 1}/{len(doc)}: {len(page_text)} chars")
    finally:
        doc.close()

    text = "\n".join(pages_text)
    if not text.strip():
        raise ValueError(
            f"OCR returned no text for {path}. "
            "PDF may be blank or contain only non-textual content (figures, "
            "stamps, illegible handwriting)."
        )
    return text


# ----------------------------------------------------------------------------
# Textract fallback (opt-in)
# ----------------------------------------------------------------------------

def ocr_pdf_textract(file_path: str | Path) -> str:
    """Run AWS Textract on a PDF, return concatenated text.

    Opt-in fallback. Textract is much better than Tesseract on tables,
    forms, and degraded scans, but bills per page. Use when Tesseract
    output is known-bad.

    Requires boto3 + AWS credentials with textract:DetectDocumentText
    permission. Uses synchronous DetectDocumentText (limited to single-page
    images); for multi-page PDFs we render to images per-page and call
    DetectDocumentText on each, matching the Tesseract code path.

    Args:
        file_path: path to the PDF.

    Returns:
        Plain text, pages joined with single newlines.

    Raises:
        FileNotFoundError: if path doesn't exist.
        ValueError: if PDF can't be opened or Textract returns nothing.
        ImportError: if boto3 isn't installed.
        botocore.exceptions.ClientError: on AWS auth or quota errors.
    """
    try:
        import boto3
    except ImportError as e:
        raise ImportError(
            "boto3 required for Textract fallback. Install with: pip install boto3"
        ) from e

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    client = boto3.client("textract")

    try:
        doc = fitz.open(path)
    except Exception as e:
        raise ValueError(f"Could not open PDF for Textract {path}: {e}") from e

    pages_text = []
    try:
        for page_num, page in enumerate(doc):
            img = _render_page_to_image(page, dpi=300)
            buf = BytesIO()
            img.save(buf, format="PNG")
            response = client.detect_document_text(Document={"Bytes": buf.getvalue()})
            page_lines = [
                block["Text"]
                for block in response.get("Blocks", [])
                if block.get("BlockType") == "LINE"
            ]
            page_text = "\n".join(page_lines)
            pages_text.append(page_text)
            log.info(f"Textract page {page_num + 1}/{len(doc)}: {len(page_text)} chars")
    finally:
        doc.close()

    text = "\n".join(pages_text)
    if not text.strip():
        raise ValueError(f"Textract returned no text for {path}.")
    return text


# ----------------------------------------------------------------------------
# Default entry point
# ----------------------------------------------------------------------------

def ocr_pdf(file_path: str | Path, use_textract: bool = False, dpi: int = 300) -> str:
    """OCR a PDF. Tesseract by default; Textract if use_textract=True.

    Args:
        file_path: path to the PDF.
        use_textract: if True, use AWS Textract instead of Tesseract.
        dpi: render DPI (Tesseract only; Textract uses its own resolution).

    Returns:
        Plain text.
    """
    if use_textract:
        return ocr_pdf_textract(file_path)
    return ocr_pdf_tesseract(file_path, dpi=dpi)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python parsers/ocr_engine.py <path-to-pdf> [--textract]")
        sys.exit(1)
    use_textract = "--textract" in sys.argv
    text = ocr_pdf(sys.argv[1], use_textract=use_textract)
    print(f"Extracted {len(text)} characters from {sys.argv[1]}")
    print(f"Engine: {'Textract' if use_textract else 'Tesseract'}")
    print("--- first 500 chars ---")
    print(text[:500])