"""Tests for parsers/pdf_parser.py."""

from pathlib import Path
import pytest

from parsers.pdf_parser import parse_pdf


# Pick the first synthetic PDF that exists, so this test runs anywhere
DOC_DIR = Path("data/synthetic/documents")
PDFS = sorted(DOC_DIR.glob("*.pdf"))


@pytest.fixture
def sample_pdf() -> Path:
    if not PDFS:
        pytest.skip("No synthetic PDFs found in data/synthetic/documents/")
    return PDFS[0]


def test_parse_pdf_returns_non_empty_text(sample_pdf):
    text = parse_pdf(sample_pdf)
    assert isinstance(text, str)
    assert len(text) > 50, "expected some real text from a clinical doc"


def test_parse_pdf_contains_expected_clinical_words(sample_pdf):
    text = parse_pdf(sample_pdf).lower()
    expected_any = ["patient", "nhs", "dob"]
    assert any(w in text for w in expected_any), (
        f"none of {expected_any} found in extracted text"
    )


def test_parse_pdf_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        parse_pdf("data/synthetic/documents/__does_not_exist__.pdf")


def test_parse_pdf_non_pdf_raises(tmp_path: Path):
    """Hand the parser a file that exists but isn't a PDF."""
    fake = tmp_path / "not_a_pdf.txt"
    fake.write_text("This is plain text, not a PDF.")
    with pytest.raises(ValueError):
        parse_pdf(fake)


def test_parse_pdf_directory_raises(tmp_path: Path):
    """A directory path should fail too."""
    with pytest.raises(ValueError):
        parse_pdf(tmp_path)