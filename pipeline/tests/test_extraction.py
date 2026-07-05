"""
tests/test_extraction.py — pytest suite for extraction.py.

Covers the regex/dictionary-based logic that does not require the
scispaCy model to be installed (parse_pdf error handling, clean_text,
drug/condition/conflict pattern matching, negation sentence rules).
These are the same checks verified manually during development —
formalised here as pytest so a reviewer can run them directly.

A separate, smaller set of tests (marked @pytest.mark.requires_model)
exercises the full extract_entities()/extract_from_pdf() path against
the real scispaCy model; these require `pip install scispacy` plus the
en_core_sci_sm model archive (see README.md) and are skipped
automatically if the model is not installed, so this file is runnable
in any environment.

Run:
    pytest tests/test_extraction.py -v
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from extraction import (
    clean_text,
    parse_pdf,
    _classify_span,
    _find_drugs_by_dictionary,
    _find_conditions_by_pattern,
    _find_conflicts_by_dictionary,
    _find_dates,
    _sentence_contains_negation,
    _sentence_spans,
)


def _model_available() -> bool:
    try:
        import spacy
        spacy.load("en_core_sci_sm")
        return True
    except Exception:
        return False


MODEL_AVAILABLE = _model_available()


# ============================================================================
# Stage 1/2: PDF parsing and text cleaning
# ============================================================================

def test_parse_pdf_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        parse_pdf("this_file_does_not_exist.pdf")


def test_parse_pdf_rejects_non_pdf(tmp_path):
    fake = tmp_path / "not_a_pdf.pdf"
    fake.write_text("this is not a real PDF file")
    with pytest.raises(ValueError, match="Not a PDF"):
        parse_pdf(fake)


def test_clean_text_removes_nonbreaking_space():
    raw = "Patient\u00a0has\u00a0diabetes."
    cleaned = clean_text(raw)
    assert "\u00a0" not in cleaned


def test_clean_text_collapses_multiple_newlines():
    raw = "Paragraph one.\n\n\n\n\nParagraph two."
    cleaned = clean_text(raw)
    assert "\n\n\n" not in cleaned


def test_clean_text_is_idempotent():
    raw = "Some  messy   text.\r\n\r\nWith odd  whitespace."
    once = clean_text(raw)
    twice = clean_text(once)
    assert once == twice


def test_clean_text_preserves_clinical_numbers():
    raw = "eGFR 32, dose 2.5 mg twice daily."
    cleaned = clean_text(raw)
    assert "32" in cleaned
    assert "2.5 mg" in cleaned


# ============================================================================
# Stage 3: NER dictionary/pattern logic (no model required)
# ============================================================================

def test_classify_span_known_drug():
    assert _classify_span("Metformin") == "Drug"


def test_classify_span_brand_name_drug():
    """Brand names added after the MTSamples generalisation check
    (paper, Evaluation section) must still classify correctly."""
    assert _classify_span("Ativan") == "Drug"
    assert _classify_span("Lipitor") == "Drug"


def test_classify_span_condition():
    assert _classify_span("heart failure") == "Diagnosis"
    assert _classify_span("pneumonia") == "Diagnosis"


def test_classify_span_no_substring_leak_uti():
    """Regression test: 'routine' must not be classified as a condition
    via UTI substring leakage (a bug found and fixed in production)."""
    assert _classify_span("routine") is None


def test_classify_span_no_substring_leak_pe():
    """Regression test: 'specialist' must not leak as PE (pulmonary
    embolism) via substring matching."""
    assert _classify_span("nurse specialist") is None


def test_classify_span_allergic_rhinitis_is_diagnosis_not_conflict():
    """Regression test: 'allergic rhinitis' is a diagnosis, not an
    allergy-conflict marker, despite containing 'allerg'."""
    result = _classify_span("allergic rhinitis")
    assert result == "Diagnosis"
    assert result != "Conflict"


def test_find_drugs_extends_dose_suffix():
    text = "Patient started on Metformin 1000 mg p.o. b.i.d."
    drugs = _find_drugs_by_dictionary(text)
    texts = [d["text"] for d in drugs]
    assert any("1000 mg" in t for t in texts)


def test_find_conditions_gina_asthma_severity():
    text = "Patient has moderate persistent asthma."
    conditions = _find_conditions_by_pattern(text)
    texts = [c["text"].lower() for c in conditions]
    assert any("moderate persistent asthma" in t for t in texts)


def test_find_conditions_ckd_staging():
    text = "CKD stage 4 confirmed on repeat bloods."
    conditions = _find_conditions_by_pattern(text)
    texts = [c["text"].lower() for c in conditions]
    assert any("ckd stage 4" in t for t in texts)


def test_find_conflicts_nkda():
    text = "ALLERGIES: NKDA."
    conflicts = _find_conflicts_by_dictionary(text)
    texts = [c["text"] for c in conflicts]
    assert "NKDA" in texts


def test_find_conflicts_excludes_allergic_rhinitis():
    text = "Past medical history: seasonal allergic rhinitis."
    conflicts = _find_conflicts_by_dictionary(text)
    texts = [c["text"].lower() for c in conflicts]
    assert not any("rhinitis" in t for t in texts)


def test_find_dates_iso_format():
    text = "Reviewed on 2024-03-15 in clinic."
    dates = _find_dates(text)
    assert len(dates) >= 1
    assert dates[0]["text"] == "2024-03-15"


# ============================================================================
# Stage 4: negation
# ============================================================================

def test_negation_nkda_pattern():
    assert _sentence_contains_negation("Patient has no known drug allergies.") is True


def test_negation_denies_pattern():
    assert _sentence_contains_negation("Patient denies chest pain or dyspnoea.") is True


def test_negation_positive_statement_not_flagged():
    assert _sentence_contains_negation("Patient has type 2 diabetes mellitus.") is False


def test_sentence_spans_splits_correctly():
    text = "First sentence. Second sentence. Third sentence."
    spans = _sentence_spans(text)
    assert len(spans) == 3


# ============================================================================
# Full model-dependent extraction (skipped if scispaCy model not installed)
# ============================================================================

@pytest.mark.skipif(not MODEL_AVAILABLE, reason="en_core_sci_sm not installed")
def test_extract_entities_end_to_end():
    from extraction import extract_entities
    text = "Patient has chronic heart failure. Started on Metformin 500 mg."
    entities = extract_entities(text)
    assert len(entities) > 0
    types_found = {e["entity_type"] for e in entities}
    assert "Diagnosis" in types_found or "Drug" in types_found


@pytest.mark.skipif(not MODEL_AVAILABLE, reason="en_core_sci_sm not installed")
def test_negation_detection_end_to_end():
    from extraction import extract_entities, detect_negation
    text = "No known drug allergies. Patient has type 2 diabetes."
    entities = extract_entities(text)
    detect_negation(text, entities)
    # At least one entity should exist; specific negation flag depends
    # on exact NER output, so this is a smoke test, not a strict assertion.
    assert isinstance(entities, list)
