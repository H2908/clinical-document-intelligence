"""Task 7: run the 8-case test set against the new _flag_key matcher.

Gates the rest of paper Day 5. The 4 MUST_STAY_DISTINCT cases are
load-bearing - they prove the new identity rule does not over-merge.
"""
from evaluation.metrics import _flag_key
from paper.config.flag_identity_test_cases import (
    run_tests,
    MUST_MERGE,
    MUST_STAY_DISTINCT,
)


def matcher(a: dict, b: dict) -> bool:
    """Two flags match iff their canonical keys are equal."""
    return _flag_key(a) == _flag_key(b)


def main() -> int:
    print("Running 8-case flag-identity test set against _flag_key...")
    print()
    print(f"  Cases that must MERGE:         {len(MUST_MERGE)}")
    print(f"  Cases that must STAY DISTINCT: {len(MUST_STAY_DISTINCT)}")
    print()

    passes, fails, failures = run_tests(matcher)
    total = passes + fails

    if fails == 0:
        print(f"[OK] {passes}/{total} passed")
        print()
        print("4/4 MUST_STAY_DISTINCT cases passed - the matcher does not")
        print("over-merge. This is the load-bearing gate per supervisor.")
        return 0

    print(f"[FAIL] {passes}/{total} passed, {fails} failed:")
    print()
    for f in failures:
        print(f)
    print()
    print("STOPPING. Matcher does not satisfy the spec. Do not regenerate")
    print("smoke or run coverage until this is fixed.")
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())