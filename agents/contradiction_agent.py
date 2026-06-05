"""
Contradiction agent — Task 4 (Phase 3). Patient-safety critical.

Compares facts across documents. Surfaces conflicts like NKDA in one
document vs penicillin allergy in another. Uses Claude for reasoning.
"""
from __future__ import annotations


def find_contradictions(
    patient_id: str,
    entities: list[dict],
    documents: list[dict],
) -> list[dict]:
    """STUB — Task 4 will implement. Returns empty for now."""
    return []
