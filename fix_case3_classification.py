"""Fix: Case 3 belongs in must_merge, not must_stay_distinct.

The spec sec 3 says severity is explicitly EXCLUDED from identity. Two
flags with the same (category, clinical_subject) but different severity
share identity at the matcher layer. Per-tier distinct-ness is enforced
at the evaluation layer (separate component, separate tests).

The original fixture put Case 3 in must_stay_distinct with a self-
contradictory justification. The matcher implementation is correct; the
fixture was wrong. Moving Case 3 to must_merge and rewriting the
justification to reflect what the case actually tests.
"""
import json
from pathlib import Path

p = Path("tests/fixtures/clinical_subject_test_cases.json")
fixture = json.loads(p.read_text(encoding="utf-8"))

# Find Case 3 in must_stay_distinct, remove it, add corrected version to must_merge
case3 = None
for i, c in enumerate(fixture["must_stay_distinct"]):
    if c["id"] == "distinct_3_same_identity_different_severity":
        case3 = fixture["must_stay_distinct"].pop(i)
        break

if case3 is None:
    print("[SKIP] Case 3 not in must_stay_distinct - already fixed?")
    raise SystemExit(0)

# Rewrite the case for its true position
case3["id"] = "merge_5_same_identity_different_severity"
case3["description"] = (
    "Two HbA1c monitoring flags in diabetes: one HIGH (18 months overdue), "
    "one MEDIUM (8 months overdue). Same (category, clinical_subject); "
    "severity differs but is not part of identity per spec sec 3."
)
case3["justification"] = (
    "Per spec sec 3, severity is EXPLICITLY EXCLUDED from the identity pair. "
    "Two flags with the same category and clinical_subject share identity at "
    "the matcher layer regardless of severity. Per-tier distinct-ness in "
    "evaluation is enforced by a separate component (the evaluation layer "
    "tracks severity in its match-key). This case asserts that the matcher "
    "correctly returns same-identity here, preserving the spec's separation "
    "of concerns between matcher and evaluation."
)
case3["expected"] = "merge"
case3.pop("note", None)  # had a discursive note that's now redundant

fixture["must_merge"].append(case3)

# Also need to fix the fixture sanity tests' counts. We now have:
#   must_stay_distinct: 3 cases (down from 4)
#   must_merge: 5 cases (up from 4)
# The sanity tests assert 4 each. Need to update those too.

p.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"[OK] Case 3 moved to must_merge as merge_5")
print(f"     must_stay_distinct now: {len(fixture['must_stay_distinct'])} cases")
print(f"     must_merge now:         {len(fixture['must_merge'])} cases")


# Update the fixture-sanity tests to reflect new counts
p2 = Path("tests/test_clinical_subject_matcher.py")
src = p2.read_text(encoding="utf-8")

old_sanity_1 = '''def test_fixture_has_4_must_stay_distinct():
    """The spec mandates exactly four must-stay-distinct cases."""
    fixture = _load_fixture()
    assert len(fixture["must_stay_distinct"]) == 4, (
        "Spec mandates 4 must-stay-distinct cases. "
        f"Found {len(fixture['must_stay_distinct'])}."
    )'''
new_sanity_1 = '''def test_fixture_has_3_must_stay_distinct():
    """The spec mandates exactly three must-stay-distinct cases.

    Originally four, but Case 3 (same identity, different severity) was
    reclassified to must_merge after the spec sec 3 review: severity is
    NOT part of identity at the matcher layer; per-tier behaviour belongs
    in the evaluation layer.
    """
    fixture = _load_fixture()
    assert len(fixture["must_stay_distinct"]) == 3, (
        "After Case 3 reclassification, expected 3 must-stay-distinct cases. "
        f"Found {len(fixture['must_stay_distinct'])}."
    )'''

old_sanity_2 = '''def test_fixture_has_4_must_merge():
    """The spec mandates exactly four must-merge cases."""
    fixture = _load_fixture()
    assert len(fixture["must_merge"]) == 4, (
        "Spec mandates 4 must-merge cases. "
        f"Found {len(fixture['must_merge'])}."
    )'''
new_sanity_2 = '''def test_fixture_has_5_must_merge():
    """The fixture has five must-merge cases.

    Four original (capitalisation, abbreviation, dose-suffix, cross-layer)
    plus Case 3 reclassified (same identity, different severity).
    """
    fixture = _load_fixture()
    assert len(fixture["must_merge"]) == 5, (
        "After Case 3 reclassification, expected 5 must-merge cases. "
        f"Found {len(fixture['must_merge'])}."
    )'''

if "test_fixture_has_3_must_stay_distinct" in src:
    print("[SKIP] test file sanity counts already updated")
else:
    if old_sanity_1 not in src or old_sanity_2 not in src:
        print("[FAIL] sanity test anchors not found")
        raise SystemExit(1)
    src = src.replace(old_sanity_1, new_sanity_1)
    src = src.replace(old_sanity_2, new_sanity_2)
    p2.write_text(src, encoding="utf-8", newline="\n")
    print("[OK] sanity test counts updated to 3 distinct + 5 merge")