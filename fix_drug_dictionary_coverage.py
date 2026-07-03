"""Expand DRUG_NAMES to cover the generic and brand-name drugs found
missing during the MTSamples generalisation check.

Found via manual inspection of raw text: pneumonia_copd_discharge listed
15 medications, pipeline extracted 2. afib_consult listed 9, pipeline
extracted 2. Root cause: DRUG_NAMES was built around UK generic names
seen in our synthetic patients and never expanded for US-style
transcription text (brand names common, wider generic vocabulary).

Adding both missing generics AND common US brand names as direct
DRUG_NAMES entries (not a brand->generic mapping - out of scope for
this fix; entity EXTRACTION correctness matters here, not clinical
normalisation).
"""
from pathlib import Path

p = Path("nlp/medical_ner.py")
src = p.read_text(encoding="utf-8")

# Find the DRUG_NAMES set as it currently stands (after earlier
# dapagliflozin-era expansion) and add the newly-found gaps.
old = '''    # CKD / nephrology
    "cinacalcet", "sevelamer", "alfacalcidol",
}'''

new = '''    # CKD / nephrology
    "cinacalcet", "sevelamer", "alfacalcidol",
    # Generics missing from original UK-focused list (found via
    # MTSamples generalisation check)
    "digoxin", "lisinopril", "prednisone", "clindamycin", "labetalol",
    "phenytoin", "docusate", "simvastatin", "glipizide", "diltiazem",
    "lorazepam", "insulin", "warfarin", "heparin", "morphine",
    "hydrochlorothiazide", "amiodarone", "clopidogrel", "pantoprazole",
    # Common US brand names (found via MTSamples generalisation check).
    # Extraction-layer only - normalised_value still reflects raw span
    # text; brand-to-generic mapping is a separate future improvement.
    "ativan", "glucotrol", "cardizem", "cardizem cd", "lipitor",
    "norvasc", "colace", "dilantin", "renagel", "sensipar", "zocor",
    "coumadin", "lasix", "prilosec", "protonix", "plavix", "toprol",
    "glucophage",
}'''

if old not in src:
    print("[FAIL] anchor not found")
    raise SystemExit(1)
src = src.replace(old, new, 1)
p.write_text(src, encoding="utf-8", newline="\n")
print("[OK] DRUG_NAMES expanded: 19 generics + 17 brand names added")

import ast
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

test_text = (
    "DISCHARGE MEDICATIONS: 1. Ativan 1 mg p.o. t.i.d. "
    "2. Metformin 1000 mg p.o. b.i.d. 3. Glucotrol 5 mg p.o. daily. "
    "4. Cardizem CD 180 mg p.o. q.a.m. 5. Lipitor 10 mg p.o. bedtime. "
    "6. Digoxin 0.25 mg p.o. daily. 7. Lisinopril 20 mg p.o. q.a.m. "
    "8. Prednisone 40 mg p.o. q.a.m. 9. Clindamycin 300 mg p.o. q.i.d."
)
entities = extract_entities(test_text)
drugs = [e["text"] for e in entities if e["entity_type"] == "Drug"]
print(f"\nTest extraction: {len(drugs)} drugs found (expect close to 9)")
for d in drugs:
    print(f"  {d}")