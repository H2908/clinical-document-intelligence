"""Tests for parsers/pdf_parser.py."""

from pathlib import Path
import pytest

from parsers.pdf_parser import parse_pdf
from parsers.text_cleaner import clean_text


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

# -------------------- text_cleaner tests --------------------

def test_clean_empty_string():
    assert clean_text("") == ""


def test_clean_collapses_multiple_spaces():
    assert clean_text("Patient   has    diabetes") == "Patient has diabetes"


def test_clean_strips_trailing_whitespace_per_line():
    assert clean_text("line one   \nline two   ") == "line one\nline two"


def test_clean_normalises_line_endings():
    assert clean_text("a\r\nb\rc") == "a\nb\nc"


def test_clean_collapses_many_newlines_to_paragraph():
    assert clean_text("para one\n\n\n\npara two") == "para one\n\npara two"


def test_clean_preserves_paragraph_breaks():
    assert clean_text("para one\n\npara two") == "para one\n\npara two"


def test_clean_replaces_nbsp_with_space():
    # U+00A0 = non-breaking space; PyMuPDF emits these often
    assert clean_text("2.5\u00a0mg") == "2.5 mg"


def test_clean_preserves_greek_beta():
    """β-lactams must survive — critical for allergy/drug detection."""
    assert "β" in clean_text("Avoid β-lactams")


def test_clean_preserves_clinical_numbers():
    text = "Metformin 1 g BD, eGFR 42, BP 128/78"
    cleaned = clean_text(text)
    assert "1 g" in cleaned
    assert "42" in cleaned
    assert "128/78" in cleaned


def test_clean_is_idempotent():
    raw = "Patient    has\r\n\r\n\r\ndiabetes   "
    once = clean_text(raw)
    twice = clean_text(once)
    assert once == twice        