"""Fix Issues 2 and 4 in nlp/medical_ner.py.

Issue 2: _find_conditions_by_pattern has corrupted regex patterns from the
         previous patch (string delimiters mangled during interpolation).
         Rewrite the function with correct patterns.

Issue 4: The _DIAGNOSIS_NOUNS exclusion logic works in isolation but the
         continue statement is inside the wrong scope in the patched code.
         Rewrite _find_conflicts_by_dictionary with the exclusion correctly
         placed BEFORE the append.
"""
from pathlib import Path
import re
import ast

p = Path("nlp/medical_ner.py")
src = p.read_text(encoding="utf-8")

# ============================================================================
# Issue 2: Replace the entire _find_conditions_by_pattern function
# ============================================================================

# Find the function start and end
func_start = src.find("def _find_conditions_by_pattern(text: str) -> list[Entity]:")
if func_start == -1:
    print("[FAIL] _find_conditions_by_pattern not found")
    raise SystemExit(1)

# Find the next function definition after it
func_end = src.find("\ndef _find_conflicts_by_dictionary", func_start)
if func_end == -1:
    print("[FAIL] could not find end of _find_conditions_by_pattern")
    raise SystemExit(1)

correct_function = r'''def _find_conditions_by_pattern(text: str) -> list[Entity]:
    """Pattern-based condition extraction for disease-classification statements
    that scispaCy en_core_sci_sm misses (GINA/CKD/HF/GOLD classifications)."""
    CLASSIFICATION_PATTERNS = [
        re.compile(
            r"\b(mild\s+intermittent|mild\s+persistent|moderate\s+persistent"
            r"|severe\s+persistent)\s+asthma\b",
            re.IGNORECASE,
        ),
        re.compile(r"\bCKD\s+stage\s+[1-5][ab]?\b", re.IGNORECASE),
        re.compile(
            r"\bchronic\s+kidney\s+disease\s+stage\s+[1-5][ab]?\b",
            re.IGNORECASE,
        ),
        re.compile(r"\bHF(?:rEF|pEF|mrEF)\b"),
        re.compile(r"\bNYHA\s+class\s+[IViv]+\b", re.IGNORECASE),
        re.compile(r"\bGOLD\s+(?:stage\s+)?[1-4]\b", re.IGNORECASE),
    ]
    found: list[Entity] = []
    for pat in CLASSIFICATION_PATTERNS:
        for match in pat.finditer(text):
            span_text = match.group(0)
            if "\n" in span_text or "\r" in span_text:
                continue
            found.append(Entity(
                entity_type="Diagnosis",
                text=span_text,
                start_offset=match.start(),
                end_offset=match.end(),
                negated=False,
                icd10_code=None,
                bnf_code=None,
                normalised_value=span_text.lower().strip(),
            ))
    return found
'''

src = src[:func_start] + correct_function + src[func_end:]
print("[OK] Issue 2: _find_conditions_by_pattern rewritten with correct regex patterns")


# ============================================================================
# Issue 4: Rewrite the conflict loop inside _find_conflicts_by_dictionary
# to correctly place the exclusion check
# ============================================================================

old_conflict_loop = '''    # Issue 4: diagnosis nouns that follow 'allerg*' — these are diagnoses,
    # not allergy-conflict markers (e.g. 'allergic rhinitis', 'allergic asthma')
    _DIAGNOSIS_NOUNS = re.compile(
        r"\\ballerg\\w*\\s+(?:rhinitis|conjunctivitis|asthma|dermatitis"
        r"|eczema|urticaria|bronchitis|sinusitis)\\b",
        re.IGNORECASE,
    )

    for pat in CONFLICT_PHRASES:
        for match in re.finditer(pat, text, flags=re.IGNORECASE):
            start, end = match.start(), match.end()
            # Issue 4: check if this match is part of a diagnosis compound
            context = text[max(0, start - 5):min(len(text), end + 30)]
            if _DIAGNOSIS_NOUNS.search(context):
                continue'''

new_conflict_loop = '''    _DIAGNOSIS_NOUNS = re.compile(
        r"\\ballerg\\w*\\s+(?:rhinitis|conjunctivitis|asthma|dermatitis"
        r"|eczema|urticaria|bronchitis|sinusitis)\\b",
        re.IGNORECASE,
    )

    for pat in CONFLICT_PHRASES:
        for match in re.finditer(pat, text, flags=re.IGNORECASE):
            start, end = match.start(), match.end()
            span_text_check = text[start:end]
            context = text[max(0, start - 5):min(len(text), end + 30)]
            if _DIAGNOSIS_NOUNS.search(context):
                continue'''

if old_conflict_loop not in src:
    # Try to find what's actually there
    idx = src.find("for pat in CONFLICT_PHRASES:")
    print(f"[DEBUG] CONFLICT_PHRASES loop at char {idx}")
    print(f"[DEBUG] Context:\n{src[idx:idx+400]}")
    print("[FAIL] conflict loop anchor not found — may need manual inspection")
    raise SystemExit(1)

src = src.replace(old_conflict_loop, new_conflict_loop, 1)
print("[OK] Issue 4: _DIAGNOSIS_NOUNS exclusion loop rewritten with correct scope")

# ============================================================================
# Write and verify
# ============================================================================
p.write_text(src, encoding="utf-8", newline="\n")

try:
    ast.parse(src)
    print("[OK] AST valid")
except SyntaxError as e:
    print(f"[FAIL] SyntaxError: {e}")
    raise SystemExit(1)

# Verify all regex patterns compile
print("\nVerifying regex patterns compile...")
try:
    import nlp.medical_ner as _mod
    import importlib
    importlib.reload(_mod)
    print("[OK] module reloads without error")
except Exception as e:
    print(f"[FAIL] module reload: {e}")
    raise SystemExit(1)
