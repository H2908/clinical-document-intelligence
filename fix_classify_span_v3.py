"""Fix Issue 4 by direct line-number surgery. Uses a single-line regex
string to avoid all quoting issues."""
from pathlib import Path
import ast, sys

p = Path("nlp/medical_ner.py")
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)

# Find CONFLICT_MARKERS check line
target_line = None
for i, line in enumerate(lines):
    if "if any(m in lower for m in CONFLICT_MARKERS):" in line:
        target_line = i
        break

if target_line is None:
    print("[FAIL] CONFLICT_MARKERS check line not found")
    raise SystemExit(1)

print(f"[OK] Found target at line {target_line + 1}")

# Write the insertion as a single line — no nested quotes, no line breaks
# The regex pattern as a raw string using chr() for special chars
insertion_lines = []
insertion_lines.append("    import re as _re2\n")
insertion_lines.append("    _diag_nouns = r\"\\ballerg\\w*\\s+(?:rhinitis|conjunctivitis|asthma|dermatitis|eczema|urticaria|bronchitis|sinusitis)\\b\"\n")
insertion_lines.append("    if _re2.search(_diag_nouns, lower, _re2.IGNORECASE):\n")
insertion_lines.append("        return \"Diagnosis\"\n")
insertion_lines.append("\n")

lines = lines[:target_line] + insertion_lines + lines[target_line:]
result = "".join(lines)

try:
    ast.parse(result)
    print("[OK] AST valid")
except SyntaxError as e:
    print(f"[FAIL] SyntaxError: {e}")
    # Show the problematic lines
    for i, ln in enumerate(result.splitlines()[260:280], start=261):
        print(f"  {i}: {ln}")
    raise SystemExit(1)

p.write_text(result, encoding="utf-8", newline="\n")
print("[OK] File written")

# Inline test — clear module cache
for mod in list(sys.modules):
    if "medical_ner" in mod or mod == "nlp":
        del sys.modules[mod]

from nlp.medical_ner import extract_entities

e = extract_entities(
    "Past Medical History: seasonal allergic rhinitis. Allergies: NKDA."
)
conflicts = [
    x["text"] for x in e
    if x["entity_type"] == "Conflict" and not x.get("negated")
]
rhinitis = [t for t in conflicts if "rhinitis" in t.lower()]
print(f"Non-negated conflicts: {conflicts}")
print(f"[{'OK' if not rhinitis else 'FAIL'}] Issue 4: rhinitis excluded")
