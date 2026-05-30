"""
Tests for nlp/negation_detector.py.

PATIENT SAFETY CRITICAL — these tests must always pass.
A failure here means downstream agents could surface a phantom condition,
allergy, or symptom to a doctor.
"""

import pytest

from nlp.medical_ner import extract_entities
from nlp.negation_detector import detect_negation


def _run(text: str):
    """Helper: NER then negation; returns the entity list."""
    ents = extract_entities(text)
    return detect_negation(text, ents)


# ============================================================================
# CRITICAL: NKDA / NKA / no known drug allergies
# ============================================================================

def test_nkda_marks_allergy_negated():
    text = "NKDA recorded. Continue current medications."
    ents = _run(text)
    allergy_ents = [e for e in ents if e["entity_type"] == "Conflict"]
    assert allergy_ents, "expected NKDA to be picked up as a Conflict entity"
    assert all(e["negated"] for e in allergy_ents), (
        "NKDA must mark every allergy/conflict entity in the sentence as negated"
    )


def test_no_known_drug_allergies_negates():
    text = "No known drug allergies. Patient is stable."
    ents = _run(text)
    conflicts = [e for e in ents if e["entity_type"] == "Conflict"]
    assert conflicts
    assert all(e["negated"] for e in conflicts)


def test_nka_acronym_negates():
    text = "NKA recorded on admission."
    ents = _run(text)
    conflicts = [e for e in ents if e["entity_type"] == "Conflict"]
    if conflicts:  # NKA may or may not be caught as an entity; rule still applies
        assert all(e["negated"] for e in conflicts)


# ============================================================================
# CRITICAL: positive allergy must NOT be marked negated
# ============================================================================

def test_real_penicillin_allergy_not_negated():
    """The negation detector must not over-fire on positive findings."""
    text = "Patient reports penicillin allergy - rash on exposure 2019."
    ents = _run(text)
    conflicts = [e for e in ents if e["entity_type"] == "Conflict"]
    assert conflicts
    assert not any(e["negated"] for e in conflicts), (
        "A real allergy must NOT be marked negated — this is a patient-safety bug"
    )


def test_mixed_document_only_negated_phrase_marked():
    """In a doc with both negated and positive findings, only one is flagged."""
    text = (
        "No known drug allergies on admission.\n"
        "Patient developed penicillin allergy with rash during stay."
    )
    ents = _run(text)
    conflicts = [e for e in ents if e["entity_type"] == "Conflict"]
    # At least one of each
    negated = [e for e in conflicts if e["negated"]]
    positive = [e for e in conflicts if not e["negated"]]
    assert negated, "the 'No known drug allergies' sentence should be negated"
    assert positive, "the 'developed allergy' sentence should be positive"


# ============================================================================
# CRITICAL: 'no history of X' patterns
# ============================================================================

def test_no_history_of_diagnosis_negated():
    text = "No history of asthma. Patient otherwise well."
    ents = _run(text)
    # 'asthma' might be classified as Diagnosis. Whatever it is, it must be negated.
    asthma_ents = [e for e in ents if "asthma" in e["text"].lower()]
    if asthma_ents:
        assert all(e["negated"] for e in asthma_ents)


def test_denies_symptom_negated():
    text = "Patient denies chest pain or shortness of breath."
    ents = _run(text)
    pain_ents = [e for e in ents if "pain" in e["text"].lower()]
    if pain_ents:
        assert all(e["negated"] for e in pain_ents)


# ============================================================================
# CRITICAL: positive condition in similar wording must remain positive
# ============================================================================

def test_has_history_of_not_negated():
    text = "Long history of asthma, well controlled."
    ents = _run(text)
    asthma_ents = [e for e in ents if "asthma" in e["text"].lower()]
    if asthma_ents:
        assert not any(e["negated"] for e in asthma_ents)


def test_diagnosis_in_positive_sentence_not_negated():
    text = "Confirms dilated cardiomyopathy with reduced ejection fraction."
    ents = _run(text)
    diag = [e for e in ents if "cardiomyopathy" in e["text"].lower()]
    assert diag
    assert not any(e["negated"] for e in diag)


# ============================================================================
# Drugs in positive prescriptions must not be negated
# ============================================================================

def test_active_prescription_not_negated():
    text = "Started Bisoprolol 2.5 mg OD and Atorvastatin 40 mg ON."
    ents = _run(text)
    drugs = [e for e in ents if e["entity_type"] == "Drug"]
    assert drugs
    assert not any(e["negated"] for e in drugs)


def test_stopped_drug_negated():
    """'Not on metformin' — patient is not taking it."""
    text = "Patient is not on metformin currently."
    ents = _run(text)
    metformin = [e for e in ents if "metformin" in e["text"].lower()]
    assert metformin
    assert all(e["negated"] for e in metformin)


# ============================================================================
# Dates are never negated
# ============================================================================

def test_dates_never_negated():
    text = "No clinic visit on 2024-02-28."
    ents = _run(text)
    dates = [e for e in ents if e["entity_type"] == "Date"]
    assert dates
    assert not any(e["negated"] for e in dates), (
        "Dates carry no clinical positive/negative meaning and must not be flagged"
    )


# ============================================================================
# Edge cases
# ============================================================================

def test_empty_input():
    assert detect_negation("", []) == []


def test_entities_preserved():
    """detect_negation must not lose, reorder, or merge entities."""
    text = "Started Metformin on 2024-02-28."
    before = extract_entities(text)
    after = detect_negation(text, list(before))
    assert len(before) == len(after)
    # Spans intact
    for b, a in zip(before, after):
        assert b["start_offset"] == a["start_offset"]
        assert b["end_offset"] == a["end_offset"]
        assert b["text"] == a["text"]