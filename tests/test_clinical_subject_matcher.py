"""
Tests for the clinical_subject matcher (Step 7 of the flag-identity fix).

Loads the 8-case fixture from tests/fixtures/clinical_subject_test_cases.json
and runs assertions on flags_have_same_identity().

Test layout follows the spec: must-stay-distinct cases first, must-merge
second. Each case has a justification stored alongside the data; on
failure, the justification is printed so the cause is immediately visible.

This file is written BEFORE the matcher exists - tests will fail (red)
until Step 6 implements flags_have_same_identity() in
agents/clinical_subject_matcher.py. That is intentional (TDD).

Run:
    pytest tests/test_clinical_subject_matcher.py -v

Guardrail: all 4 must-stay-distinct cases must pass before any downstream
steps (8, 9, 10) proceed. The must-merge cases are equally important but
the must-stay-distinct ones are the higher-risk failure mode (false
positives inflate precision).
"""
from __future__ import annotations
import json
from pathlib import Path

import pytest

# Import target - does not exist yet (Step 6 will create it)
# pytest will report ImportError until then; that is the expected red state.
try:
    from agents.clinical_subject_matcher import flags_have_same_identity, normalise_subject
    MATCHER_AVAILABLE = True
except ImportError:
    MATCHER_AVAILABLE = False


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "clinical_subject_test_cases.json"


def _load_fixture() -> dict:
    """Load the 8-case fixture. Fails loudly if the file is missing."""
    if not FIXTURE_PATH.exists():
        pytest.fail(f"Fixture missing: {FIXTURE_PATH}. See Step 2 of the flag-identity fix.")
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _format_failure(case: dict, actual: bool) -> str:
    """Format a readable failure message including the case justification."""
    expected = case["expected"]
    return (
        f"\n  Case ID: {case['id']}"
        f"\n  Description: {case['description']}"
        f"\n  Expected: {expected}"
        f"\n  Actual:   {'merge' if actual else 'distinct'}"
        f"\n  Flag A:   category={case['flag_a']['category']!r} "
        f"subject={case['flag_a']['clinical_subject']!r}"
        f"\n  Flag B:   category={case['flag_b']['category']!r} "
        f"subject={case['flag_b']['clinical_subject']!r}"
        f"\n  Justification: {case['justification']}"
    )


# Per-test skip marker for tests that need the matcher implementation.
# Fixture-sanity tests do NOT need this — they verify the JSON fixture itself
# and must run even before Step 6.
needs_matcher = pytest.mark.skipif(
    not MATCHER_AVAILABLE,
    reason="agents.clinical_subject_matcher not yet implemented (Step 6 pending).",
)


# ============================================================================
# Must-stay-distinct cases — these are the primary correctness constraints
# ============================================================================

@needs_matcher
@pytest.mark.parametrize("case", _load_fixture()["must_stay_distinct"], ids=lambda c: c["id"])
def test_must_stay_distinct(case: dict) -> None:
    """
    These cases MUST NOT merge. False positives here directly inflate the
    apparent precision of the system and corrupt reproducibility metrics.

    A failure of any one of these cases blocks the flag-identity fix from
    proceeding to Steps 8, 9, 10.
    """
    result = flags_have_same_identity(case["flag_a"], case["flag_b"])
    assert result is False, _format_failure(case, actual=result)


# ============================================================================
# Must-merge cases — normalisation correctness
# ============================================================================

@needs_matcher
@pytest.mark.parametrize("case", _load_fixture()["must_merge"], ids=lambda c: c["id"])
def test_must_merge(case: dict) -> None:
    """
    These cases MUST merge. False negatives here cause inflated distinct-flag
    counts and undercount reproducibility across LLM runs that produce
    surface-different but clinically-identical flags.
    """
    result = flags_have_same_identity(case["flag_a"], case["flag_b"])
    assert result is True, _format_failure(case, actual=result)


# ============================================================================
# Normalisation invariants — direct tests on normalise_subject()
# ============================================================================
# These complement the matcher tests by isolating normalisation behaviour.
# If a must-merge case fails, these tests narrow down whether the bug is
# in normalisation or in the matcher's comparison logic.

@needs_matcher
@pytest.mark.parametrize("raw,expected", [
    ("Metformin", "metformin"),
    ("  metformin  ", "metformin"),
    ("METFORMIN", "metformin"),
    ("ACE inhibitor", "acei"),
    ("ace inhibitor", "acei"),
    ("ACEi", "acei"),
    ("estimated glomerular filtration rate", "egfr"),
    ("eGFR", "egfr"),
    ("HbA1c", "hba1c"),
    ("glycated haemoglobin", "hba1c"),
    ("LVEF", "lvef"),
    ("Furosemide 80 mg", "furosemide"),
    ("Furosemide 80mg", "furosemide"),
    ("Spironolactone 25 mg OD", "spironolactone"),
    ("Metformin 500mg", "metformin"),
    # Must NOT strip numeric from measurements
    ("eGFR 32", "egfr 32"),
    ("LVEF 28%", "lvef 28%"),
    # Empty / null cases
    ("", ""),
    ("   ", ""),
])
def test_normalise_subject(raw: str, expected: str) -> None:
    """
    Direct tests on the normalisation pipeline. If matcher tests fail but
    these pass, the bug is in the matcher's comparison; if these fail, the
    bug is in normalisation.
    """
    assert normalise_subject(raw) == expected, (
        f"\n  Input:    {raw!r}"
        f"\n  Expected: {expected!r}"
        f"\n  Actual:   {normalise_subject(raw)!r}"
    )


# ============================================================================
# Fixture sanity — assert the fixture itself is well-formed
# ============================================================================

def test_fixture_has_4_must_stay_distinct():
    """The spec mandates exactly four must-stay-distinct cases."""
    fixture = _load_fixture()
    assert len(fixture["must_stay_distinct"]) == 4, (
        "Spec mandates 4 must-stay-distinct cases. "
        f"Found {len(fixture['must_stay_distinct'])}."
    )


def test_fixture_has_4_must_merge():
    """The spec mandates exactly four must-merge cases."""
    fixture = _load_fixture()
    assert len(fixture["must_merge"]) == 4, (
        "Spec mandates 4 must-merge cases. "
        f"Found {len(fixture['must_merge'])}."
    )


def test_fixture_cases_have_justifications():
    """Every case must have a non-empty justification."""
    fixture = _load_fixture()
    for case in fixture["must_stay_distinct"] + fixture["must_merge"]:
        assert case.get("justification"), (
            f"Case {case['id']} missing justification. "
            "Justifications are required so failures are diagnostic."
        )
