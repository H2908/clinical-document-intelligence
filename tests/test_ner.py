"""Tests for nlp/medical_ner.py."""

import pytest
from nlp.medical_ner import extract_entities


# ----- Drug detection ----------------------------------------------------------

def test_finds_known_drug():
    ents = extract_entities("Patient takes Metformin 1 g BD.")
    drugs = [e for e in ents if e["entity_type"] == "Drug"]
    assert any("metformin" in e["text"].lower() for e in drugs)


def test_finds_multiple_drugs():
    text = "Current medications: Bisoprolol 2.5 mg OD, Atorvastatin 40 mg ON."
    ents = extract_entities(text)
    drugs = {e["text"].lower().split()[0] for e in ents if e["entity_type"] == "Drug"}
    assert "bisoprolol" in drugs
    assert "atorvastatin" in drugs


def test_drug_normalised_to_lowercase_base_name():
    ents = extract_entities("Started Bisoprolol 2.5 mg OD.")
    drug = next(e for e in ents if e["entity_type"] == "Drug")
    assert drug["normalised_value"] == "bisoprolol"


# ----- Conflict / allergy detection -------------------------------------------

def test_finds_penicillin_allergy_as_conflict():
    text = "Patient reports penicillin allergy - rash on exposure 2019."
    ents = extract_entities(text)
    assert any(e["entity_type"] == "Conflict" for e in ents)


def test_nkda_is_conflict():
    ents = extract_entities("NKDA recorded.")
    assert any(e["entity_type"] == "Conflict" for e in ents)


# ----- Diagnosis + ICD-10 -----------------------------------------------------

def test_finds_diagnosis():
    ents = extract_entities("Confirms dilated cardiomyopathy with LVEF 32%.")
    diags = [e for e in ents if e["entity_type"] == "Diagnosis"]
    assert any("cardiomyopathy" in e["text"].lower() for e in diags)


def test_extracts_icd10_when_present():
    text = "Echocardiogram confirms ischaemic heart disease (ICD-10: I25.9)."
    ents = extract_entities(text)
    diag = next(e for e in ents if e["entity_type"] == "Diagnosis")
    assert diag["icd10_code"] == "I25.9"


# ----- Dates ------------------------------------------------------------------

def test_finds_iso_date():
    ents = extract_entities("Reviewed on 2024-02-28.")
    dates = [e for e in ents if e["entity_type"] == "Date"]
    assert any(d["text"] == "2024-02-28" for d in dates)


def test_finds_natural_date():
    ents = extract_entities("Seen on 28 Feb 2024 in clinic.")
    dates = [e for e in ents if e["entity_type"] == "Date"]
    assert any("28 Feb 2024" in d["text"] for d in dates)


def test_finds_slash_date():
    ents = extract_entities("DOB 14/01/1970.")
    dates = [e for e in ents if e["entity_type"] == "Date"]
    assert any("14/01/1970" in d["text"] for d in dates)


# ----- Output contract --------------------------------------------------------

def test_offsets_match_source_text():
    """text[start:end] must equal the entity's text — NLP_OUTPUT.md rule."""
    text = "Started Metformin 1 g BD on 2024-02-28."
    ents = extract_entities(text)
    for e in ents:
        assert text[e["start_offset"]:e["end_offset"]] == e["text"]


def test_empty_input_returns_empty_list():
    assert extract_entities("") == []
    assert extract_entities("   \n  ") == []


def test_entities_sorted_by_position():
    text = "Started Metformin on 2024-02-28."
    ents = extract_entities(text)
    starts = [e["start_offset"] for e in ents]
    assert starts == sorted(starts)


def test_no_overlapping_entities():
    """Deduplication: no entity should overlap another."""
    text = "Started Metformin 1 g BD on 2024-02-28 for diabetes."
    ents = extract_entities(text)
    for i, a in enumerate(ents):
        for b in ents[i+1:]:
            assert a["end_offset"] <= b["start_offset"] or b["end_offset"] <= a["start_offset"]


def test_negated_field_defaults_false():
    """negation_detector will set this; medical_ner must initialise to False."""
    ents = extract_entities("Started Metformin.")
    assert all(e["negated"] is False for e in ents)