"""Test set for precision_tiered.

Six cases proving the three-tier masking behaves correctly:
  1. Tier 1 emission                 -> TP=1, FP=0, precision=1.00
  2. Tier 2 emission                 -> all masked, precision=None
  3. Tier 3 emission (unmatched)     -> TP=0, FP=1, precision=0.00
  4. Two Tier 1 emissions            -> TP=2, FP=0, precision=1.00
  5. Mixed Tier 1 + Tier 2 + Tier 3  -> TP=1, FP=1, masked=1, precision=0.50
  6. Empty emission                  -> precision=None

If any case fails, the masking design is wrong and we stop.
"""
from evaluation.metrics import precision_tiered

# Build representative flag dicts. _flag_key only uses category and
# clinical_subject so the other fields don't matter for this test.
def flag(category: str, subject: str, severity: str = "MEDIUM") -> dict:
    return {
        "category": category,
        "clinical_subject": subject,
        "severity": severity,
        "description": f"test flag for {subject}",
    }


# Gold sets - represent the tier 1 and tier 2 subjects for a hypothetical patient
TIER_1 = {
    ("ALLERGY_CONFLICT", "penicillin allergy"),
    ("OVERDUE_FOLLOWUP", "chronic kidney disease"),
}
TIER_2 = {
    ("AI_UNDOCUMENTED_TREATMENT", "sglt2 inhibitor in t2dm"),
    ("AI_INVESTIGATION_NO_RESULT", "u&e recheck post-spironolactone"),
}


def run_case(case_id: str, emitted: list[dict], expected: dict) -> tuple[bool, str]:
    """Return (passed, message)."""
    got = precision_tiered(emitted, TIER_1, TIER_2)
    for k, v in expected.items():
        if got.get(k) != v:
            return False, f"[FAIL] {case_id}: expected {k}={v!r}, got {got.get(k)!r}  full={got}"
    return True, f"[OK]   {case_id}: {got}"


CASES = [
    (
        "1_single_tier_1",
        [flag("ALLERGY_CONFLICT", "penicillin allergy", "HIGH")],
        {"true_positives": 1, "false_positives": 0, "tier_2_masked": 0, "precision": 1.0},
    ),
    (
        "2_single_tier_2_masked",
        [flag("AI_UNDOCUMENTED_TREATMENT", "sglt2 inhibitor in t2dm")],
        {"true_positives": 0, "false_positives": 0, "tier_2_masked": 1, "precision": None},
    ),
    (
        "3_single_tier_3_unmatched",
        [flag("AI_FABRICATED_FLAG", "something the doctor never wrote")],
        {"true_positives": 0, "false_positives": 1, "tier_2_masked": 0, "precision": 0.0},
    ),
    (
        "4_two_tier_1",
        [
            flag("ALLERGY_CONFLICT", "penicillin allergy", "HIGH"),
            flag("OVERDUE_FOLLOWUP", "chronic kidney disease"),
        ],
        {"true_positives": 2, "false_positives": 0, "tier_2_masked": 0, "precision": 1.0},
    ),
    (
        "5_mixed_tier_1_tier_2_tier_3",
        [
            flag("ALLERGY_CONFLICT", "penicillin allergy", "HIGH"),
            flag("AI_UNDOCUMENTED_TREATMENT", "sglt2 inhibitor in t2dm"),
            flag("AI_INVENTED_CATEGORY", "fabricated subject the docs don't support"),
        ],
        {"true_positives": 1, "false_positives": 1, "tier_2_masked": 1, "precision": 0.5},
    ),
    (
        "6_empty_emission",
        [],
        {"true_positives": 0, "false_positives": 0, "tier_2_masked": 0, "precision": None},
    ),
]


def main() -> int:
    print("Running 6-case precision_tiered test set...\n")
    passes = 0
    for case_id, emitted, expected in CASES:
        ok, msg = run_case(case_id, emitted, expected)
        print(msg)
        if ok:
            passes += 1
    print(f"\n{passes}/{len(CASES)} passed")
    return 0 if passes == len(CASES) else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())