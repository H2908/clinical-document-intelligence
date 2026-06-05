"""
Flag agent — Task 3 (Phase 3). Patient-safety critical.

Applies clinical rules + LLM reasoning to surface risk flags.
Examples: Metformin + low eGFR -> drug-safety flag, overdue referrals.
"""
from __future__ import annotations


def detect_flags(
    patient_id: str,
    entities: list[dict],
    documents: list[dict],
) -> list[dict]:
    """STUB — Task 3 will implement. Returns empty for now."""
    return []