"""Apply the validated Guard 3 fix to agents/flag_agent.py.

Two changes, both validated offline against 5 regression cases
(test_guard3_regression.py, 5/5 pass) before being applied here:

1. Tokenizer: include numeric and unit tokens (already fixed in a
   prior pass on this file - this script checks it's still present
   and is a no-op if so).

2. Threshold logic: replace the old dead-code double-OR condition
   (which always effectively required longest_run >= NGRAM_FLOOR
   regardless of quote length, making short quotes structurally
   unable to pass) with: required_run = min(NGRAM_FLOOR,
   len(quote_tokens)). Short quotes must be FULLY contiguous (100%
   of their own tokens); long quotes still need >= NGRAM_FLOOR
   contiguous tokens. No loophole: a short quote can only pass by
   being genuinely, entirely contiguous in the source.

Found via MTSamples generalisation testing: dose-only quotes like
'Metformin 1000 mg' (3 tokens) could never reach a 5-token contiguous
run and were always rejected as composition-fabrication regardless of
whether they were genuinely verbatim. Regression-tested against the
NYHA composition-fabrication example (must still reject) and the
eGFR/echocardiogram paraphrase examples (must still accept) before
being applied.
"""
from pathlib import Path

p = Path("agents/flag_agent.py")
src = p.read_text(encoding="utf-8")

# Confirm tokenizer fix is still in place (from earlier pass)
if "_UNIT_TOKENS = {" not in src:
    print("[WARN] Tokenizer fix not found - was it reverted? Check manually.")
else:
    print("[OK] Tokenizer fix already present (numeric/unit tokens included)")

# Fix the threshold logic
old = '''            # Tier 1b - contiguous n-gram floor
            longest_run = _longest_contiguous_match(quote_tokens, cited_tokens)
            ngram_required = max(NGRAM_FLOOR, len(quote_tokens) // 2)
            if longest_run < min(NGRAM_FLOOR, ngram_required) or longest_run < min(NGRAM_FLOOR, max(1, len(quote_tokens) // 2)):'''

new = '''            # Tier 1b - contiguous n-gram floor
            # Fixed after MTSamples spot-check: the previous double-OR
            # condition was dead code that always effectively required
            # longest_run >= NGRAM_FLOOR regardless of quote length,
            # making short quotes (e.g. "Metformin 1000 mg", 3 tokens)
            # structurally unable to pass even when genuinely, fully
            # contiguous in the source. Fix: short quotes must match
            # FULLY (100% of their own tokens); long quotes still need
            # >= NGRAM_FLOOR contiguous tokens. No loophole - a short
            # quote can only pass by being entirely contiguous.
            longest_run = _longest_contiguous_match(quote_tokens, cited_tokens)
            required_run = min(NGRAM_FLOOR, len(quote_tokens))
            if longest_run < required_run:'''

count = src.count(old)
print(f"Threshold anchor occurrences found: {count}")
if count == 0:
    print("[FAIL] threshold anchor not found - may have different whitespace")
    raise SystemExit(1)
src = src.replace(old, new)
print(f"[OK] threshold logic fixed ({count} occurrence)")

p.write_text(src, encoding="utf-8", newline="\n")

import ast
try:
    ast.parse(src)
    print("[OK] AST valid")
except SyntaxError as e:
    print(f"[FAIL] {e}")
    raise SystemExit(1)

print("\nFix applied. Re-run test_guard3_regression.py conceptually validated this")
print("threshold change already; next step is a live pipeline re-run on MTSamples.")
