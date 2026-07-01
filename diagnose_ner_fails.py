"""Diagnose why Issues 2 and 4 fixes aren't working."""
import re

# --- Issue 2 ---
print("=== Issue 2 diagnosis ===")
text2 = "Assessment: consistent with moderate persistent asthma (GINA classification, step 3)."
pat2 = re.compile(
    r"\b(mild\s+intermittent|mild\s+persistent|moderate\s+persistent"
    r"|severe\s+persistent)\s+asthma\b",
    re.IGNORECASE,
)
matches = list(pat2.finditer(text2))
print(f"Pattern matches: {[m.group(0) for m in matches]}")
print(f"Text being searched: {text2!r}")

# Check if the function exists and is callable
from nlp.medical_ner import extract_entities
import nlp.medical_ner as ner_mod
print(f"_find_conditions_by_pattern exists: {hasattr(ner_mod, '_find_conditions_by_pattern')}")
if hasattr(ner_mod, '_find_conditions_by_pattern'):
    result = ner_mod._find_conditions_by_pattern(text2)
    print(f"Direct call result: {result}")

# --- Issue 4 ---
print("\n=== Issue 4 diagnosis ===")
text4 = "Past Medical History: seasonal allergic rhinitis. Allergies: NKDA."
CONFLICT_PHRASES = [
    r"drug\s+allerg\w*",
    r"\ballerg\w+",
    r"\bintoleran\w+",
    r"\bNKDA\b",
    r"\bNKA\b",
]
_DIAGNOSIS_NOUNS = re.compile(
    r"\ballerg\w*\s+(?:rhinitis|conjunctivitis|asthma|dermatitis"
    r"|eczema|urticaria|bronchitis|sinusitis)\b",
    re.IGNORECASE,
)
for pat in CONFLICT_PHRASES:
    for match in re.finditer(pat, text4, flags=re.IGNORECASE):
        start, end = match.start(), match.end()
        context = text4[max(0, start - 5):min(len(text4), end + 30)]
        diagnosis_match = _DIAGNOSIS_NOUNS.search(context)
        print(f"Match: {match.group(0)!r} at {start}:{end}")
        print(f"  Context: {context!r}")
        print(f"  _DIAGNOSIS_NOUNS hit: {diagnosis_match}")