"""Tests for nlp/date_normaliser.py."""

from datetime import date
import pytest

from nlp.medical_ner import extract_entities
from nlp.date_normaliser import normalise_dates


def _dates(text, doc_date=None):
    """Helper: NER + date normalisation; return only Date entities."""
    ents = extract_entities(text)
    normalise_dates(ents, doc_date)
    return [e for e in ents if e["entity_type"] == "Date"]


# ============================================================================
# Absolute date formats
# ============================================================================

def test_iso_date_normalises_to_itself():
    dates = _dates("Reviewed on 2024-02-28.")
    assert dates
    assert dates[0]["normalised_value"] == "2024-02-28"


def test_natural_date_normalises():
    dates = _dates("Seen on 28 Feb 2024 in clinic.")
    assert dates
    assert dates[0]["normalised_value"] == "2024-02-28"


def test_slash_date_uk_format():
    """UK: 14/01/2024 must be 14 January (DMY), not 1 April."""
    dates = _dates("DOB 14/01/2024.")
    assert dates
    assert dates[0]["normalised_value"] == "2024-01-14"


def test_long_month_name():
    dates = _dates("Admitted on 5 September 2023.")
    assert dates
    assert dates[0]["normalised_value"] == "2023-09-05"


# ============================================================================
# Relative phrases (need a document_date)
# ============================================================================

def test_relative_weeks_ago():
    doc_date = date(2024, 4, 10)
    dates = _dates("Follow-up was 4 weeks ago.", doc_date=doc_date)
    # 4 weeks before 10 April 2024 = 13 March 2024
    assert dates
    assert dates[0]["normalised_value"] == "2024-03-13"


def test_relative_in_future():
    doc_date = date(2024, 4, 10)
    dates = _dates("Refer to heart failure nurse within 2 weeks.", doc_date=doc_date)
    # 2 weeks after 10 April 2024 = 24 April 2024
    assert dates
    assert dates[0]["normalised_value"] == "2024-04-24"


def test_relative_without_document_date_left_unresolved():
    """If no document_date is supplied, relative phrases can't be resolved."""
    dates = _dates("Follow-up in 2 weeks.")
    # The phrase '2 weeks' is unlikely to match an absolute date either,
    # so normalised_value should remain None.
    if dates:
        for d in dates:
            # Either it was matched as a Date entity but stayed unresolved,
            # or it wasn't found at all — both are acceptable.
            if d["text"].lower().strip().startswith("2 weeks"):
                assert d["normalised_value"] is None


# ============================================================================
# Edge cases
# ============================================================================

def test_no_date_in_text():
    ents = extract_entities("Patient was reviewed in clinic.")
    normalise_dates(ents)
    dates = [e for e in ents if e["entity_type"] == "Date"]
    assert dates == []


def test_already_normalised_not_overwritten():
    """If normalised_value is pre-set, don't overwrite."""
    ents = extract_entities("Seen on 2024-02-28.")
    for e in ents:
        if e["entity_type"] == "Date":
            e["normalised_value"] = "MANUAL-OVERRIDE"
    normalise_dates(ents)
    dates = [e for e in ents if e["entity_type"] == "Date"]
    assert dates[0]["normalised_value"] == "MANUAL-OVERRIDE"


def test_multiple_dates_all_normalised():
    text = "First seen 14/01/2024, follow-up 28 Feb 2024, next review 2024-04-10."
    dates = _dates(text)
    iso_values = {d["normalised_value"] for d in dates}
    assert "2024-01-14" in iso_values
    assert "2024-02-28" in iso_values
    assert "2024-04-10" in iso_values


def test_non_date_entities_untouched():
    """The normaliser must not modify Drug or Diagnosis entities."""
    ents = extract_entities("Started Bisoprolol on 2024-02-28.")
    normalise_dates(ents)
    for e in ents:
        if e["entity_type"] == "Drug":
            # We set normalised_value to lowercase drug name in NER;
            # it must remain that way.
            assert e["normalised_value"] == "bisoprolol"


def test_empty_entity_list():
    assert normalise_dates([]) == []
    assert normalise_dates([], date(2024, 1, 1)) == []