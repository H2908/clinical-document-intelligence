"""Fix Issue 4 at source: add diagnosis-noun exclusion to _classify_span.
scispaCy returns 'seasonal allergic rhinitis' as an entity span;
_classify_span sees 'allerg' and returns Conflict. Fix: check for
diagnosis-noun compounds before the CONFLICT_MARKERS check.
"""
from pathlib import Path
import ast

p = Path("nlp/medical_ner.py")
src = p.read_text(encoding="utf-8")

old = '''    # Conflict markers
    if any(m in lower for m in CONFLICT_MARKERS):
        return "Conflict"'''

new = '''    # Diagnosis-noun compounds containing allerg* are diagnoses, not conflicts.
    # e.g. "allergic rhinitis", "seasonal allergic rhinitis", "allergic asthma"
    _DIAG_NOUN_RE = re.compile(
        r"\ballerg\w*\s+(?:rhinitis|conjunctivitis|asthma|dermatitis"
        r"|eczema|urticaria|bronchitis|sinusitis)\b",
        re.IGNORECASE,
    )
    if _DIAG_NOUN_RE.search(lower):
        return "Diagnosis"

    # Conflict markers
    if any(m in lower for m in CONFLICT_MARKERS):
        return "Conflict"'''

if old not in src:
    print("[FAIL] anchor not found")
    raise SystemExit(1)
src = src.replace(old, new, 1)
p.write_text(src, encoding="utf-8", newline="\n")

try:
    ast.parse(src)
    print("[OK] AST valid")
except SyntaxError as e:
    print(f"[FAIL] {e}")
    raise SystemExit(1)

import sys
for mod in list(sys.modules):
    if "medical_ner" in mod:
        del sys.modules[mod]
from nlp.medical_ner import extract_entities

e4 = extract_entities("Past Medical History: seasonal allergic rhinitis. Allergies: NKDA.")
non_neg = [x["text"] for x in e4 if x["entity_type"] == "Conflict" and not x.get("negated")]
rhinitis = [t for t in non_neg if "rhinitis" in t.lower()]
print(f"[{'OK' if not rhinitis else 'FAIL'}] Issue 4: non-negated conflicts = {non_neg}")