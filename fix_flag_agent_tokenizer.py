"""Fix the LOCAL, nested _content_tokens closure inside
agents/flag_agent.py's hybrid validator - this is the function actually
executed at runtime, distinct from evaluation/grounding.py's module-level
twin (already fixed, but not in this call path).

Same root cause and fix as the earlier evaluation/grounding.py patch:
tokens = re.findall(r"[a-z]{4,}", ...) drops all digits and short unit
tokens, collapsing 'Metformin 1000 mg' to a single token and making a
genuine contiguous match structurally undetectable.
"""
from pathlib import Path

p = Path("agents/flag_agent.py")
src = p.read_text(encoding="utf-8")

old = '''            def _content_tokens(text: str) -> list[str]:
                """Tokenise to lowercase content tokens (>=4 chars, alpha, not stopwords)."""
                tokens = re.findall(r"[a-z]{4,}", text.lower())
                return [t for t in tokens if t not in STOPWORDS_AND_GENERIC]'''

new = '''            def _content_tokens(text: str) -> list[str]:
                """Tokenise to lowercase content tokens for contiguous-run
                matching. Includes alphabetic tokens >=4 chars, numeric
                tokens (dose numbers), and short clinical unit tokens
                (mg, mcg, ml, iu etc). Fixed after MTSamples spot-check
                found the alpha-only version silently dropped dose
                numbers, collapsing 'Metformin 1000 mg' to a single
                token and capping longest-run at 1 regardless of true
                quote fidelity."""
                _UNIT_TOKENS = {"mg", "mcg", "ml", "iu", "kg", "cm"}
                lower = text.lower()
                combined_pattern = r"[a-z]{4,}|\\b\\d+(?:\\.\\d+)?\\b|\\b(?:mg|mcg|ml|iu|kg|cm)\\b"
                all_tokens = re.findall(combined_pattern, lower)
                return [t for t in all_tokens if t not in STOPWORDS_AND_GENERIC]'''

count = src.count(old)
print(f"Occurrences found: {count}")
if count == 0:
    print("[FAIL] anchor not found")
    raise SystemExit(1)
src = src.replace(old, new)
print(f"[OK] local _content_tokens fixed ({count} occurrence)")

p.write_text(src, encoding="utf-8", newline="\n")

import ast
try:
    ast.parse(src)
    print("[OK] AST valid")
except SyntaxError as e:
    print(f"[FAIL] {e}")
    raise SystemExit(1)