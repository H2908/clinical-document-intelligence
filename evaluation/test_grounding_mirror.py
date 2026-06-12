"""
Mirror test: evaluation/grounding.py must produce identical verdicts to
the frozen v1.3 validator in agents/flag_agent.py.

This test runs the 6-case graded test set (from graded_test_cases.py) through
evaluation.grounding.grade_flag() and asserts each verdict matches the
expected verdict from the original graded set.

If this test fails, the two implementations have drifted. Fix grounding.py
to match flag_agent.py — never the other way around (flag_agent.py is the
frozen instrument).

Usage:
    python -m evaluation.test_grounding_mirror

Returns exit 0 on pass, 1 on any mismatch.
"""
import sys
from pathlib import Path

# Import the frozen graded test set from the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from graded_test_cases import GRADED_CASES, DOCUMENTS  # noqa: E402
from evaluation.grounding import grade_flag  # noqa: E402


def main() -> int:
    print("=" * 75)
    print("MIRROR TEST — evaluation/grounding.py vs frozen v1.3 instrument")
    print("=" * 75)
    print()

    fail_count = 0
    for case in GRADED_CASES:
        # Construct a flag dict from the graded case
        flag = {
            "category":           case["category"],
            "description":        case["description"],
            "cited_document_id":  case["cited_document_id"],
            "source_quote":       case["source_quote"],
        }
        result = grade_flag(flag, DOCUMENTS)
        got = result["verdict"]
        expected = case["expected_verdict"]

        # The borderline case has a flexible expected verdict
        if expected == "fabrication_or_borderline":
            passed = got in ("fabrication", "composition-fabrication", "paraphrase")
        else:
            passed = (got == expected)

        status = "PASS" if passed else "FAIL"
        if not passed:
            fail_count += 1
        print(f"[{status}] {case['case_id']}")
        print(f"  expected: {expected}")
        print(f"  got:      {got}")
        print(f"  overlap:  {result['overlap_cited']:.2f}")
        print(f"  longest_run: {result['longest_run']}")
        if result["best_other_doc"]:
            print(f"  best_other: {result['best_other_doc']} = {result['best_other_overlap']:.2f}")
        print()

    print("=" * 75)
    if fail_count == 0:
        print(f"PASS — all {len(GRADED_CASES)} cases produced the expected verdict")
        print("=" * 75)
        return 0
    print(f"FAIL — {fail_count} of {len(GRADED_CASES)} cases mismatched")
    print("=" * 75)
    return 1


if __name__ == "__main__":
    sys.exit(main())