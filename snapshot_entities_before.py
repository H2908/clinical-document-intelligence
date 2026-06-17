"""Capture the current entity output on patient_001 doc 01 as a baseline.

After we tighten the NER, we diff against this snapshot to confirm we
removed false positives without removing true positives.
"""
import json
from pathlib import Path
from parsers.pdf_parser import parse_pdf
from nlp.medical_ner import extract_entities

text = parse_pdf("data/synthetic/documents/patient_001/01_GP_Referral_Thompson_12Jan2024.pdf")
entities = extract_entities(text)

out = Path("ner_baseline_before_fix.json")
out.write_text(json.dumps(entities, indent=2), encoding="utf-8")

print(f"Wrote {out}")
print(f"Total entities: {len(entities)}")
from collections import Counter
print(f"By type: {Counter(e['entity_type'] for e in entities)}")
diagnoses = [e for e in entities if e['entity_type'] == 'Diagnosis']
print(f"\nDiagnoses (n={len(diagnoses)}):")
for e in diagnoses:
    print(f"  {e['text']!r:<50} code={e['icd10_code']!r}  conf={e['normalised_value']!r}")