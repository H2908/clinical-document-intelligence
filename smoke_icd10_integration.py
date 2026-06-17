"""Smoke test for ICD-10 mapper integration.

Tests three things:
  1. Explicit codes in documents still win (no regression).
  2. The mapper fallback fires for diagnoses without explicit codes.
  3. Drug, Date, Conflict entities are unaffected (no icd10_code).
"""
from nlp.medical_ner import extract_entities

# Case 1: explicit code in trailing window - should match regex
text1 = "Patient has chronic heart failure (ICD-10: I50.22) on optimal therapy."
entities1 = extract_entities(text1)
print("Case 1 - explicit ICD-10 code in text:")
for e in entities1:
    if e["entity_type"] == "Diagnosis":
        print(f"  {e['text']!r} -> code={e['icd10_code']} ({e['normalised_value']})")

# Case 2: no explicit code - should fall back to mapper
text2 = "Patient diagnosed with type 2 diabetes mellitus 3 years ago. Reports good metformin adherence."
entities2 = extract_entities(text2)
print("\nCase 2 - no explicit code (mapper fallback):")
for e in entities2:
    if e["entity_type"] == "Diagnosis":
        print(f"  {e['text']!r} -> code={e['icd10_code']} ({e['normalised_value']})")

# Case 3: full clinical letter from synthetic data
print("\nCase 3 - real synthetic document:")
from parsers.pdf_parser import parse_pdf
real_text = parse_pdf("data/synthetic/documents/patient_001/01_GP_Referral_Thompson_12Jan2024.pdf")
entities3 = extract_entities(real_text)
diagnoses = [e for e in entities3 if e["entity_type"] == "Diagnosis"]
with_code = [e for e in diagnoses if e["icd10_code"] is not None]
explicit = [e for e in diagnoses if e["normalised_value"] == "explicit"]
mapper_high = [e for e in diagnoses if e["normalised_value"] == "mapper-high"]
mapper_med = [e for e in diagnoses if e["normalised_value"] == "mapper-medium"]
no_code = [e for e in diagnoses if e["icd10_code"] is None]
print(f"  Diagnoses total: {len(diagnoses)}")
print(f"  With ICD-10 code: {len(with_code)}  ({len(with_code)/max(len(diagnoses),1)*100:.0f}%)")
print(f"    explicit:     {len(explicit)}")
print(f"    mapper-high:  {len(mapper_high)}")
print(f"    mapper-medium: {len(mapper_med)}")
print(f"  No code: {len(no_code)}")
if with_code:
    print(f"\n  Sample assignments:")
    for e in with_code[:8]:
        print(f"    {e['text']!r:<50} -> {e['icd10_code']:<8} ({e['normalised_value']})")