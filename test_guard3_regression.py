"""Offline regression test for Guard 3 (composition-fabrication /
contiguous n-gram check), using the exact known dev-set examples from
evaluation/analysis_verified.ipynb and docs/PAPER_NOTES.md.

Runs entirely offline - no API calls, no LLM. Tests the local
_content_tokens / _longest_contiguous_match logic directly by
reproducing the calculation inline, since those are closures nested
inside agents/flag_agent.py and not independently importable.

MUST pass before AND after any Guard 3 threshold fix. This is the
non-negotiable gate for Option B (fixing the composition-fabrication
false-positive found via MTSamples testing).
"""
import re

STOPWORDS_AND_GENERIC = {
    "patient", "documented", "noted", "listed", "verify", "confirm",
    "doctor", "with", "that", "this", "from", "have", "been", "were",
}


def content_tokens_OLD(text: str) -> list[str]:
    """The ORIGINAL (buggy) tokenizer - alpha only, >=4 chars."""
    tokens = re.findall(r"[a-z]{4,}", text.lower())
    return [t for t in tokens if t not in STOPWORDS_AND_GENERIC]


def content_tokens_NEW(text: str) -> list[str]:
    """The FIXED tokenizer - includes numeric and unit tokens."""
    lower = text.lower()
    combined_pattern = r"[a-z]{4,}|\b\d+(?:\.\d+)?\b|\b(?:mg|mcg|ml|iu|kg|cm)\b"
    all_tokens = re.findall(combined_pattern, lower)
    return [t for t in all_tokens if t not in STOPWORDS_AND_GENERIC]


def longest_contiguous_match(a: list[str], b: list[str]) -> int:
    if not a or not b:
        return 0
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    best = 0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
                if dp[i][j] > best:
                    best = dp[i][j]
    return best


NGRAM_FLOOR = 5


def old_threshold_check(quote_tokens, longest_run):
    """The ORIGINAL threshold logic (has the dead-code second clause)."""
    ngram_required = max(NGRAM_FLOOR, len(quote_tokens) // 2)
    fails = (
        longest_run < min(NGRAM_FLOOR, ngram_required)
        or longest_run < min(NGRAM_FLOOR, max(1, len(quote_tokens) // 2))
    )
    return not fails  # True = passes (grounded)


def new_threshold_check(quote_tokens, longest_run):
    """PROPOSED fix: short quotes must be FULLY contiguous (100% of their
    own tokens); long quotes need at least NGRAM_FLOOR contiguous tokens.
    This is strictly at least as strict as the old rule for long quotes,
    and is the only way a short quote can ever pass - by being entirely,
    genuinely contiguous, not partially so. No loophole: you cannot game
    this by using an artificially short quote, since a short quote must
    match itself in full."""
    required_run = min(NGRAM_FLOOR, len(quote_tokens))
    return longest_run >= required_run


# ============================================================================
# Regression cases - known dev-set examples with EXPECTED verdicts
# ============================================================================

CASES = [
    {
        "name": "NYHA composition-fabrication (docs/PAPER_NOTES.md, worked example 1)",
        "quote": "NYHA class II consistent with heart failure therapy",
        "doc_text": (
            "Patient reports symptoms consistent with NYHA class II. "
            "Plan: Continue current heart failure therapy."
        ),
        "expected_grounded": False,  # MUST still be rejected after fix
    },
    {
        "name": "eGFR paraphrase (docs/PAPER_NOTES.md, accepted-as-grounded example)",
        "quote": "bloods including eGFR in 4 weeks",
        "doc_text": "Routine bloods including U&E, eGFR in 4 weeks",
        "expected_grounded": True,  # MUST still pass after fix
    },
    {
        "name": "echocardiogram terse instruction (Day 2 verified verbatim example)",
        "quote": "Repeat echocardiogram in 6 months",
        "doc_text": "Plan: 3. Repeat echocardiogram in 6 months",
        "expected_grounded": True,  # MUST still pass - real verbatim example
    },
    {
        "name": "Metformin dose-only quote (NEW - the MTSamples false-positive)",
        "quote": "Metformin 1000 mg",
        "doc_text": "3. Metformin 1000 mg p.o. b.i.d.",
        "expected_grounded": True,  # This is THE case the fix targets
    },
    {
        "name": "Digoxin dose-only quote (NEW - MTSamples false-positive)",
        "quote": "Digoxin 0.25 mg",
        "doc_text": "6. Digoxin 0.25 mg p.o. daily.",
        "expected_grounded": True,
    },
]

print(f"{'Case':<65} {'Old tok/OldThresh':<20} {'New tok/NewThresh':<20} {'Expected':<10}")
print("-" * 120)

all_pass = True
for case in CASES:
    quote = case["quote"]
    doc_text = case["doc_text"]
    expected = case["expected_grounded"]

    # OLD tokenizer + OLD threshold (reproduces the original bug)
    old_q = content_tokens_OLD(quote)
    old_d = content_tokens_OLD(doc_text)
    old_run = longest_contiguous_match(old_q, old_d)
    old_result = old_threshold_check(old_q, old_run)

    # NEW tokenizer + NEW threshold (the proposed fix)
    new_q = content_tokens_NEW(quote)
    new_d = content_tokens_NEW(doc_text)
    new_run = longest_contiguous_match(new_q, new_d)
    new_result = new_threshold_check(new_q, new_run)

    status = "OK" if new_result == expected else "MISMATCH"
    if new_result != expected:
        all_pass = False

    print(f"{case['name']:<65} {f'{old_result} (run={old_run})':<20} "
          f"{f'{new_result} (run={new_run})':<20} {str(expected):<10} [{status}]")

print()
if all_pass:
    print("[OK] ALL REGRESSION CASES PASS under proposed fix. Safe to apply.")
else:
    print("[FAIL] At least one regression case does NOT match expected behaviour.")
    print("       DO NOT apply this fix as-is. Investigate mismatches above.")
