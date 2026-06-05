"""
Briefing agent — Task 5 (Phase 3).

Synthesises everything (entities, timeline, flags, contradictions) into
one administrative briefing for the pre-appointment screen.
NOT clinical advice — explicit admin-use-only framing.
"""
from __future__ import annotations


def build_briefing(
    patient_id: str,
    entities: list[dict],
    documents: list[dict],
    timeline_events: list[dict],
    flags: list[dict],
    contradictions: list[dict],
) -> dict:
    """STUB — Task 5 will implement. Returns empty briefing for now."""
    return {
        "patient_id": patient_id,
        "summary": "",
        "active_conditions": [],
        "current_medications": [],
        "recent_results": [],
        "open_flags": [],
        "generated_at": None,
    }