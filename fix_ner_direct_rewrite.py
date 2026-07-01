"""Direct rewrite of the two corrupted functions in nlp/medical_ner.py.
Uses start/end character positions to replace the corrupted blocks exactly.
"""
from pathlib import Path
import ast

p = Path("nlp/medical_ner.py")
src = p.read_text(encoding="utf-8")

# ============================================================================
# Find and replace _find_conditions_by_pattern (corrupted)
# ============================================================================
start_marker = "def _find_conditions_by_pattern(text: str) -> list[Entity]:"
end_marker = "def _find_conflicts_by_dictionary(text: str) -> list[Entity]:"

start_idx = src.find(start_marker)
end_idx = src.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("[FAIL] Could not locate function boundaries")
    raise SystemExit(1)

good_conditions_fn = (
    'def _find_conditions_by_pattern(text: str) -> list[Entity]:\n'
    '    """Pattern-based condition extraction for disease-classification\n'
    '    statements that scispaCy en_core_sci_sm misses."""\n'
    '    import re as _re\n'
    '    PATS = [\n'
    '        _re.compile(\n'
    '            r"\\b(mild\\s+intermittent|mild\\s+persistent'\
    '|moderate\\s+persistent|severe\\s+persistent)\\s+asthma\\b",\n'
    '            _re.IGNORECASE,\n'
    '        ),\n'
    '        _re.compile(r"\\bCKD\\s+stage\\s+[1-5][ab]?\\b", _re.IGNORECASE),\n'
    '        _re.compile(\n'
    '            r"\\bchronic\\s+kidney\\s+disease\\s+stage\\s+[1-5][ab]?\\b",\n'
    '            _re.IGNORECASE,\n'
    '        ),\n'
    '        _re.compile(r"\\bHF(?:rEF|pEF|mrEF)\\b"),\n'
    '        _re.compile(r"\\bNYHA\\s+class\\s+[IViv]+\\b", _re.IGNORECASE),\n'
    '        _re.compile(r"\\bGOLD\\s+(?:stage\\s+)?[1-4]\\b", _re.IGNORECASE),\n'
    '    ]\n'
    '    found: list[Entity] = []\n'
    '    for pat in PATS:\n'
    '        for match in pat.finditer(text):\n'
    '            span = match.group(0)\n'
    '            if "\\n" in span or "\\r" in span:\n'
    '                continue\n'
    '            found.append(Entity(\n'
    '                entity_type="Diagnosis",\n'
    '                text=span,\n'
    '                start_offset=match.start(),\n'
    '                end_offset=match.end(),\n'
    '                negated=False,\n'
    '                icd10_code=None,\n'
    '                bnf_code=None,\n'
    '                normalised_value=span.lower().strip(),\n'
    '            ))\n'
    '    return found\n'
    '\n'
)

src = src[:start_idx] + good_conditions_fn + src[end_idx:]
print("[OK] _find_conditions_by_pattern rewritten cleanly")

# ============================================================================
# Find and replace _find_conflicts_by_dictionary (corrupted _DIAGNOSIS_NOUNS)
# ============================================================================
conflicts_start = src.find("def _find_conflicts_by_dictionary(text: str) -> list[Entity]:")
conflicts_end = src.find("\ndef _find_dates(", conflicts_start)
if conflicts_start == -1 or conflicts_end == -1:
    print("[FAIL] Could not locate _find_conflicts_by_dictionary boundaries")
    raise SystemExit(1)

good_conflicts_fn = (
    'def _find_conflicts_by_dictionary(text: str) -> list[Entity]:\n'
    '    """Independent conflict/allergy pass - catches what scispaCy misses.\n'
    '    Matches allergy-related terms so the negation detector has something\n'
    '    to mark in "no known drug allergies" sentences.\n'
    '    """\n'
    '    CONFLICT_PHRASES = [\n'
    '        r"drug\\s+allerg\\w*",\n'
    '        r"\\ballerg\\w+",\n'
    '        r"\\bintoleran\\w+",\n'
    '        r"\\bNKDA\\b",\n'
    '        r"\\bNKA\\b",\n'
    '    ]\n'
    '    # Diagnosis compounds containing allerg* are NOT allergy-conflict\n'
    '    # markers (e.g. "allergic rhinitis", "allergic asthma").\n'
    '    DIAGNOSIS_NOUNS_RE = re.compile(\n'
    '        r"\\ballerg\\w*\\s+(?:rhinitis|conjunctivitis|asthma|dermatitis'\
    '|eczema|urticaria|bronchitis|sinusitis)\\b",\n'
    '        re.IGNORECASE,\n'
    '    )\n'
    '    found: list[Entity] = []\n'
    '    for pat in CONFLICT_PHRASES:\n'
    '        for match in re.finditer(pat, text, flags=re.IGNORECASE):\n'
    '            start, end = match.start(), match.end()\n'
    '            span_text = text[start:end]\n'
    '            # Skip paragraph-boundary bleed\n'
    '            if "\\n" in span_text or "\\r" in span_text:\n'
    '                continue\n'
    '            # Skip diagnosis compounds\n'
    '            context = text[max(0, start - 5):min(len(text), end + 30)]\n'
    '            if DIAGNOSIS_NOUNS_RE.search(context):\n'
    '                continue\n'
    '            found.append(Entity(\n'
    '                entity_type="Conflict",\n'
    '                text=span_text,\n'
    '                start_offset=start,\n'
    '                end_offset=end,\n'
    '                negated=False,\n'
    '                icd10_code=None,\n'
    '                bnf_code=None,\n'
    '                normalised_value=None,\n'
    '            ))\n'
    '    return found\n'
)

src = src[:conflicts_start] + good_conflicts_fn + src[conflicts_end:]
print("[OK] _find_conflicts_by_dictionary rewritten cleanly")

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

# Quick functional test
import importlib, sys
if "nlp.medical_ner" in sys.modules:
    del sys.modules["nlp.medical_ner"]
from nlp.medical_ner import extract_entities

e1 = extract_entities("Plan: Start dapagliflozin 10 mg OD.")
drugs = [x["text"] for x in e1 if x["entity_type"] == "Drug"]
print(f"[{'OK' if any('dapagliflozin' in d.lower() for d in drugs) else 'FAIL'}] Issue 1: {drugs}")

e2 = extract_entities("Assessment: consistent with moderate persistent asthma (GINA step 3).")
diags = [x["text"] for x in e2 if x["entity_type"] == "Diagnosis"]
print(f"[{'OK' if any('moderate persistent' in d.lower() for d in diags) else 'FAIL'}] Issue 2: {diags}")

e3 = extract_entities("NT-proBNP 4200 pg/mL.\nAllergies: penicillin allergy.")
bleed = [x["text"] for x in e3 if x["entity_type"] == "Conflict" and "\n" in x["text"]]
print(f"[{'OK' if not bleed else 'FAIL'}] Issue 3 bleed: {bleed}")

e4 = extract_entities("Past Medical History: seasonal allergic rhinitis. Allergies: NKDA.")
non_neg = [x["text"] for x in e4 if x["entity_type"] == "Conflict" and not x.get("negated")]
rhinitis = [t for t in non_neg if "rhinitis" in t.lower()]
print(f"[{'OK' if not rhinitis else 'FAIL'}] Issue 4 rhinitis: {non_neg}")
