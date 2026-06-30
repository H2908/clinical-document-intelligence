"""Fix Issue 4 by direct line-number surgery on _classify_span."""
from pathlib import Path
import ast

p = Path("nlp/medical_ner.py")
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)

# Find the line with the Conflict markers check
target_line = None
for i, line in enumerate(lines):
    if "if any(m in lower for m in CONFLICT_MARKERS):" in line:
        target_line = i
        break

if target_line is None:
    print("[FAIL] CONFLICT_MARKERS check line not found")
    raise SystemExit(1)

print(f"[OK] Found CONFLICT_MARKERS check at line {target_line + 1}")
print(f"     Context: {lines[target_line].rstrip()}")

# Build the insertion lines using chr() for quotes to avoid nesting issues
q = chr(34)  # double quote
b = chr(92)  # backslash

insertion = [
    f"    # Diagnosis-noun compounds: allergic rhinitis etc are diagnoses not conflicts\n",
    f"    _diag_pat = (\n",
    f"        {q}{b}ballerg{b}w*{b}s+(?:rhinitis|conjunctivitis|asthma\n",
    f"        |dermatitis|eczema|urticaria|bronchitis|sinusitis){b}b{q}\n",
    f"    )\n",
    f"    import re as _re2\n",
    f"    if _re2.search(_diag_pat, lower, _re2.IGNORECASE):\n",
    f"        return {q}Diagnosis{q}\n",
    f"\n",
]

# Insert before the CONFLICT_MARKERS check
lines = lines[:target_line] + insertion + lines[target_line:]
result = "".join(lines)

try:
    ast.parse(result)
    print("[OK] AST valid after insertion")
except SyntaxError as e:
    print(f"[FAIL] SyntaxError: {e}")
    raise SystemExit(1)

p.write_text(result, encoding="utf-8", newline="\n")
print("[OK] File written")

# Inline test
import sys
for mod in list(sys.modules):
    if "medical_ner" in mod or "nlp" in mod:
        del sys.modules[mod]

from nlp.medical_ner import extract_entities
e = extract_entities("Past Medical History: seasonal allergic rhinitis. Allergies: NKDA.")
conflicts = [x["text"] for x in e if x["entity_type"] == "Conflict" and not x.get("negated")]
rhinitis = [t for t in conflicts if "rhinitis" in t.lower()]
print(f"Non-negated conflicts: {conflicts}")
print(f"[{'OK' if not rhinitis else 'FAIL'}] Issue 4 rhinitis excluded: {rhinitis}")