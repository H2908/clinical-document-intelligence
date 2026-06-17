"""Integrate ontology.icd10_mapper into nlp/medical_ner.py.

Behaviour:
  1. _icd10_for_span first tries the existing trailing-window regex
     for explicit '(ICD-10: I50.22)' patterns in the document.
  2. If no explicit code, falls back to ontology.icd10_mapper.lookup
     on the entity text.
  3. If mapper returns a hit, the code is used; confidence is recorded
     in the entity's normalised_value field (currently unused for
     Diagnosis entities).

Pure additive: no signature changes, no behavioural change when explicit
codes are present. The existing 50-char trailing window regex still wins.
"""
from pathlib import Path

p = Path("nlp/medical_ner.py")
src = p.read_text(encoding="utf-8")

if "from ontology.icd10_mapper import" in src:
    print("[SKIP] ontology mapper already imported - nothing to do")
    raise SystemExit(0)

# ---- 1. Add the ontology import after the spacy import ----
old_import = "import spacy\nfrom spacy.language import Language"
new_import = (
    "import spacy\n"
    "from spacy.language import Language\n"
    "from ontology.icd10_mapper import lookup as _icd10_mapper_lookup"
)
if old_import not in src:
    print("[FAIL] spacy import anchor not found")
    raise SystemExit(1)
src = src.replace(old_import, new_import)

# ---- 2. Extend _icd10_for_span with mapper fallback ----
old_helper = '''def _icd10_for_span(text: str, full_text: str, start: int, end: int) -> str | None:
    window = full_text[end : end + 50]
    m = ICD10_RE.search(window)
    return m.group(1) if m else None'''

new_helper = '''def _icd10_for_span(text: str, full_text: str, start: int, end: int) -> str | None:
    """Resolve ICD-10 code for a diagnosis span.

    Two-tier:
      1. Explicit code in trailing 50-char window (existing behaviour).
         Example: "chronic heart failure (ICD-10: I50.22)" - regex hits.
      2. Fallback: ontology.icd10_mapper.lookup on the span text itself.
         Example: "chronic kidney disease stage 3b" with no explicit code
         in window - mapper returns N18.32.

    Explicit codes win because they're the document's own assertion.
    The mapper fires only when no explicit code is present.
    """
    window = full_text[end : end + 50]
    m = ICD10_RE.search(window)
    if m:
        return m.group(1)
    # Fallback: curated CSV mapper
    result = _icd10_mapper_lookup(text)
    return result["code"] if result is not None else None


def _icd10_confidence_for_span(text: str, full_text: str, start: int, end: int) -> str | None:
    """Confidence label for the ICD-10 assignment from _icd10_for_span.

    Returns 'explicit' if the document gave us the code, 'mapper-high' or
    'mapper-medium' if the curated mapper fell back, None if no code found.
    Stored in normalised_value for Diagnosis entities (which otherwise
    don't use that field).
    """
    window = full_text[end : end + 50]
    if ICD10_RE.search(window):
        return "explicit"
    result = _icd10_mapper_lookup(text)
    if result is None:
        return None
    return f"mapper-{result['confidence']}"'''

if old_helper not in src:
    print("[FAIL] _icd10_for_span helper anchor not found")
    raise SystemExit(1)
src = src.replace(old_helper, new_helper)

# ---- 3. Wire confidence into the Diagnosis entity construction ----
# The existing code sets normalised_value to the drug name for Drugs and None
# for everything else. For Diagnoses, we now store the icd10 confidence label.
old_construction = '''            icd10_code=(
                _icd10_for_span(ent.text, text, ent.start_char, ent.end_char)
                if etype == "Diagnosis" else None
            ),
            normalised_value=(
                ent.text.lower().split()[0] if etype == "Drug" else None
            ),'''

new_construction = '''            icd10_code=(
                _icd10_for_span(ent.text, text, ent.start_char, ent.end_char)
                if etype == "Diagnosis" else None
            ),
            normalised_value=(
                ent.text.lower().split()[0] if etype == "Drug"
                else _icd10_confidence_for_span(ent.text, text, ent.start_char, ent.end_char)
                if etype == "Diagnosis"
                else None
            ),'''

if old_construction not in src:
    print("[FAIL] entity construction anchor not found")
    raise SystemExit(1)
src = src.replace(old_construction, new_construction)

p.write_text(src, encoding="utf-8", newline="\n")
print("OK ontology.icd10_mapper integrated into medical_ner")
print(f"File now {len(p.read_text(encoding='utf-8').splitlines())} lines")