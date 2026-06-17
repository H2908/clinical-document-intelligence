"""After-fix snapshot. Compare to ner_baseline_before_fix.json."""
import json
from pathlib import Path
from parsers.pdf_parser import parse_pdf
from nlp.medical_ner import extract_entities

text = parse_pdf("data/synthetic/documents/patient_001/01_GP_Referral_Thompson_12Jan2024.pdf")
entities = extract_entities(text)

out = Path("ner_after_fix.json")
out.write_text(json.dumps(entities, indent=2), encoding="utf-8")

print(f"Wrote {out}")
print(f"Total entities: {len(entities)}")
from collections import Counter
print(f"By type: {Counter(e['entity_type'] for e in entities)}")
diagnoses = [e for e in entities if e['entity_type'] == 'Diagnosis']
print(f"\nDiagnoses (n={len(diagnoses)}):")
for e in diagnoses:
    print(f"  {e['text']!r:<50} code={e['icd10_code']!r}  conf={e['normalised_value']!r}")

# Quick diff against before snapshot
before_path = Path("ner_baseline_before_fix.json")
if before_path.exists():
    before = json.loads(before_path.read_text(encoding="utf-8"))
    before_dx_set = {e['text'] for e in before if e['entity_type'] == 'Diagnosis'}
    after_dx_set = {e['text'] for e in diagnoses}
    removed = before_dx_set - after_dx_set
    kept = before_dx_set & after_dx_set
    added = after_dx_set - before_dx_set
    print(f"\nDIFF vs before:")
    print(f"  Diagnoses kept:    {len(kept)}")
    for t in sorted(kept):
        print(f"    KEPT: {t!r}")
    print(f"  Diagnoses removed: {len(removed)}")
    for t in sorted(removed):
        print(f"    REMOVED: {t!r}")
    if added:
        print(f"  Diagnoses NEW:     {len(added)}")
        for t in sorted(added):
            print(f"    NEW: {t!r}")