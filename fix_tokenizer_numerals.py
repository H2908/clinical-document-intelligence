"""Fix Guard 3's tokenizer to preserve numeric tokens, so dose-only
quotes like 'Metformin 1000 mg' aren't collapsed to a single alphabetic
token, which made genuine contiguous matches structurally undetectable.

Found via MTSamples spot-check: 6/9 rejected candidates were flagged
composition-fabrication despite being verified genuinely contiguous in
the source document. Root cause: tokens = re.findall(r"[a-z]{4,}", ...)
strips all digits and any token under 4 chars, so 'Metformin 1000 mg'
-> ['metformin'] (single token), making longest-contiguous-run <= 1
structurally guaranteed regardless of actual quote fidelity.

Fix: also capture numeric tokens (dose numbers) and short unit tokens
(mg, mcg, ml, etc - clinically meaningful despite being short), so
'Metformin 1000 mg' -> ['metformin', '1000', 'mg'] and can register a
genuine 3-token contiguous run.
"""
from pathlib import Path

p = Path("evaluation/grounding.py")
src = p.read_text(encoding="utf-8")

old = '''    """Tokenise to lowercase content tokens (>=4 chars, alpha, not stopwords)."""
    tokens = re.findall(r"[a-z]{4,}", text.lower())
    return [t for t in tokens if t not in STOPWORDS_AND_GENERIC]'''

new = '''    """Tokenise to lowercase content tokens for contiguous-run matching.

    Includes: alphabetic tokens >=4 chars (content words, not stopwords),
    numeric tokens (dose numbers - clinically load-bearing, e.g. the
    '1000' in 'Metformin 1000 mg'), and short clinical unit tokens
    (mg, mcg, ml, iu etc - under 4 chars but clinically meaningful).

    Fixed after MTSamples spot-check found the alpha-only, >=4-char
    version silently dropped dose numbers, collapsing quotes like
    'Metformin 1000 mg' to a single token and making genuine contiguous
    matches structurally undetectable (longest-run capped at 1
    regardless of true quote fidelity).
    """
    UNIT_TOKENS = {"mg", "mcg", "ml", "iu", "kg", "cm"}
    lower = text.lower()
    alpha_tokens = re.findall(r"[a-z]{4,}", lower)
    numeric_tokens = re.findall(r"\\b\\d+(?:\\.\\d+)?\\b", lower)
    unit_tokens = [t for t in re.findall(r"[a-z]+", lower) if t in UNIT_TOKENS]
    # Reconstruct in original order using a single combined regex pass
    # so contiguity is preserved (critical for the n-gram-run check).
    combined_pattern = r"[a-z]{4,}|\\b\\d+(?:\\.\\d+)?\\b|\\b(?:mg|mcg|ml|iu|kg|cm)\\b"
    all_tokens = re.findall(combined_pattern, lower)
    return [t for t in all_tokens if t not in STOPWORDS_AND_GENERIC]'''

if old not in src:
    print("[FAIL] anchor not found")
    raise SystemExit(1)
src = src.replace(old, new, 1)
p.write_text(src, encoding="utf-8", newline="\n")
print("[OK] tokenizer fixed: numeric and unit tokens preserved")

import ast
try:
    ast.parse(src)
    print("[OK] AST valid")
except SyntaxError as e:
    print(f"[FAIL] {e}")
    raise SystemExit(1)