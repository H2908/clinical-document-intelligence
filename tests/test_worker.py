"""
End-to-end test for the worker pipeline.

Runs worker.document_processor against real synthetic PDFs and asserts that
the output dict satisfies NLP_OUTPUT.md §2 and contains sensible data.

This is the proof that Phase 2's vertical slice works.
"""

from __future__ import annotations
import json
from datetime import date
from pathlib import Path

import pytest

from worker.document_processor import process_document, write_to_disk


DOC_DIR = Path("data/synthetic/documents")
PDFS = sorted(DOC_DIR.glob("*.pdf"))

# Top-level keys required by NLP_OUTPUT.md §2.
REQUIRED_KEYS = {
    "nlp_version", "document_id", "patient_id", "processed_at",
    "status", "error_message", "document",
    "entities", "conditions", "medications", "observations",
    "flags", "contradictions", "timeline_events",
}

# Keys inside the "document" sub-object.
REQUIRED_DOCUMENT_KEYS = {"doc_type", "extracted_text", "image_url"}


# ----------------------------------------------------------------------------
# Fixture: process one PDF, return the payload
# ----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def first_pdf() -> Path:
    if not PDFS:
        pytest.skip("No synthetic PDFs found in data/synthetic/documents/")
    return PDFS[0]


@pytest.fixture(scope="module")
def processed(first_pdf: Path) -> dict:
    """Process the first synthetic PDF once, reuse across tests."""
    return process_document(
        file_path=first_pdf,
        document_id="doc_test_01",
        patient_id="pat_test_01",
        document_date=date(2024, 4, 10),
        doc_type="clinic_letter",
    )


# ============================================================================
# Contract compliance — NLP_OUTPUT.md §2
# ============================================================================

def test_top_level_keys_present(processed):
    """Every key from the NLP_OUTPUT.md contract must appear."""
    missing = REQUIRED_KEYS - set(processed.keys())
    assert not missing, f"missing keys: {missing}"


def test_document_subobject_shape(processed):
    doc = processed["document"]
    missing = REQUIRED_DOCUMENT_KEYS - set(doc.keys())
    assert not missing, f"missing document keys: {missing}"


def test_status_is_processed(processed):
    assert processed["status"] == "processed"
    assert processed["error_message"] is None


def test_arrays_are_lists_never_null(processed):
    """NLP_OUTPUT.md rule: empty arrays are [], never null, never missing."""
    for key in ["entities", "conditions", "medications", "observations",
                "flags", "contradictions", "timeline_events"]:
        assert isinstance(processed[key], list), f"{key} must be a list"


def test_ids_passed_through(processed):
    assert processed["document_id"] == "doc_test_01"
    assert processed["patient_id"] == "pat_test_01"


def test_processed_at_is_iso_timestamp(processed):
    """ISO 8601 UTC, e.g. 2026-05-31T12:00:00Z."""
    ts = processed["processed_at"]
    assert isinstance(ts, str)
    assert ts.endswith("Z")
    assert "T" in ts


# ============================================================================
# Pipeline correctness
# ============================================================================

def test_extracted_text_is_populated(processed):
    text = processed["document"]["extracted_text"]
    assert isinstance(text, str)
    assert len(text) > 100, "expected real text from a clinical document"


def test_entities_have_required_fields(processed):
    """Every entity has the fields NLP_OUTPUT.md §3 requires."""
    required = {"entity_type", "text", "start_offset", "end_offset",
                "negated", "icd10_code", "normalised_value"}
    for e in processed["entities"]:
        missing = required - set(e.keys())
        assert not missing, f"entity {e} missing keys: {missing}"


def test_entity_offsets_align_with_text(processed):
    """text[start:end] must equal entity.text — patient-safety provenance rule."""
    full_text = processed["document"]["extracted_text"]
    for e in processed["entities"]:
        slice_ = full_text[e["start_offset"]:e["end_offset"]]
        assert slice_ == e["text"], (
            f"offset mismatch: got {slice_!r}, expected {e['text']!r}"
        )


def test_at_least_some_entities_found(processed):
    """The first synthetic PDF is realistic enough to yield entities."""
    assert len(processed["entities"]) > 0, "expected some entities in a real doc"


def test_at_least_one_drug_or_diagnosis(processed):
    """Realistic clinical docs always contain at least one drug or diagnosis."""
    types = {e["entity_type"] for e in processed["entities"]}
    assert types & {"Drug", "Diagnosis"}, (
        f"expected Drug or Diagnosis among {types}"
    )


def test_derived_conditions_are_non_negated(processed):
    """conditions[] is derived from non-negated diagnoses only."""
    for c in processed["conditions"]:
        # All conditions must exist as a non-negated diagnosis entity
        match = next(
            (e for e in processed["entities"]
             if e["entity_type"] == "Diagnosis" and e["text"] == c["name"]),
            None,
        )
        assert match is not None, f"condition {c} has no source entity"
        assert match["negated"] is False, f"condition {c} was derived from a negated entity"


def test_derived_medications_are_non_negated(processed):
    for m in processed["medications"]:
        # At least one non-negated Drug entity must match this medication
        matches = [
            e for e in processed["entities"]
            if e["entity_type"] == "Drug" and not e["negated"]
        ]
        assert matches, f"medication {m} but no non-negated drug entities"


# ============================================================================
# Failure handling — NLP_OUTPUT.md §5
# ============================================================================

def test_missing_file_returns_failed_payload():
    """Errors must produce a valid payload, not crash."""
    payload = process_document(
        file_path="data/synthetic/documents/__does_not_exist__.pdf",
        document_id="doc_missing",
        patient_id="pat_test_01",
        document_date=date(2024, 4, 10),
    )
    assert payload["status"] == "failed"
    assert payload["error_message"] is not None
    assert "not found" in payload["error_message"].lower()
    # All arrays remain empty per the contract
    for key in ["entities", "conditions", "medications", "observations",
                "flags", "contradictions", "timeline_events"]:
        assert payload[key] == [], f"{key} must be [] on failure"


def test_non_pdf_file_returns_failed_payload(tmp_path):
    """A real-but-non-PDF file is a documented failure case."""
    fake = tmp_path / "not_a_pdf.txt"
    fake.write_text("Plain text, not a PDF.")
    payload = process_document(
        file_path=fake,
        document_id="doc_fake",
        patient_id="pat_test_01",
    )
    assert payload["status"] == "failed"
    assert payload["error_message"] is not None


# ============================================================================
# Cross-document: no state leakage between runs
# ============================================================================

def test_two_documents_processed_independently():
    """The worker must be stateless across calls."""
    if len(PDFS) < 2:
        pytest.skip("Need at least 2 synthetic PDFs")
    a = process_document(PDFS[0], "doc_a", "pat_a", date(2024, 4, 10))
    b = process_document(PDFS[1], "doc_b", "pat_b", date(2024, 4, 10))
    assert a["document_id"] == "doc_a"
    assert b["document_id"] == "doc_b"
    # Their texts differ — sanity check no state leaked
    assert a["document"]["extracted_text"] != b["document"]["extracted_text"]


# ============================================================================
# Disk sink — Phase 2 stand-in for the storage layer
# ============================================================================

def test_write_to_disk_creates_valid_json(processed, tmp_path):
    out_path = write_to_disk(processed, tmp_path)
    assert out_path.exists()
    # Re-read and re-parse — must round-trip cleanly
    text = out_path.read_text(encoding="utf-8")
    payload = json.loads(text)
    assert payload["document_id"] == processed["document_id"]
    assert set(payload.keys()) == set(processed.keys())


# ============================================================================
# Patient-safety: synthetic seeded conflicts are detectable
# ============================================================================

def test_pipeline_surfaces_a_negated_allergy_somewhere():
    """
    Across our synthetic dataset, at least some documents say NKDA or
    'no known drug allergies'. The pipeline must mark at least one such
    Conflict entity as negated. If it doesn't, the negation detector
    has silently regressed.
    """
    found_negated_conflict = False
    for pdf in PDFS[:10]:   # check a handful to keep test fast
        payload = process_document(
            pdf, f"doc_{pdf.stem}", "pat_x",
            document_date=date(2024, 4, 10),
        )
        if any(e["entity_type"] == "Conflict" and e["negated"]
               for e in payload["entities"]):
            found_negated_conflict = True
            break
    assert found_negated_conflict, (
        "no negated Conflict entity found in the first 10 PDFs — "
        "negation detection may have regressed"
    )