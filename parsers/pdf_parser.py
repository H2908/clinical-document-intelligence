"""
PDF -> text using PyMuPDF.

First stage of the worker pipeline. Takes a path to a PDF, returns plain text.
The next stage (text_cleaner) normalises whitespace and encoding; this module
deliberately does NOT clean — it stays close to what PyMuPDF returns so we can
debug parser issues separately from cleaning issues.
"""

from pathlib import Path
import fitz  # PyMuPDF

# Every real PDF starts with this magic header.
PDF_MAGIC = b"%PDF-"


def parse_pdf(file_path: str | Path) -> str:
    """
    Extract text from a PDF file.

    Args:
        file_path: path to the PDF on disk.

    Returns:
        Plain text. Pages are joined with a single newline.

    Raises:
        FileNotFoundError: if the path does not exist.
        ValueError: if the path is not a file, is not a valid PDF,
                    is encrypted, or contains no extractable text.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    if not path.is_file():
        raise ValueError(f"Not a file: {path}")

    # Check magic bytes before anything else — PyMuPDF on some platforms
    # is too lenient about what it accepts.
    with open(path, "rb") as f:
        header = f.read(5)
    if header != PDF_MAGIC:
        raise ValueError(
            f"Not a PDF (header was {header!r}, expected {PDF_MAGIC!r}): {path}"
        )

    try:
        doc = fitz.open(path)
    except Exception as e:
        raise ValueError(f"Could not open PDF {path}: {e}") from e

    try:
        if doc.is_encrypted:
            raise ValueError(f"PDF is encrypted: {path}")
        pages = [page.get_text() for page in doc]
    finally:
        doc.close()

    text = "\n".join(pages)
    if not text.strip():
        raise ValueError(
            f"No extractable text in {path}. "
            "If this is a scanned PDF, OCR is needed (Phase 4, L2)."
        )
    return text


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python parsers/pdf_parser.py <path-to-pdf>")
        sys.exit(1)
    text = parse_pdf(sys.argv[1])
    print(f"Extracted {len(text)} characters from {sys.argv[1]}")
    print("--- first 500 chars ---")
    print(text[:500])