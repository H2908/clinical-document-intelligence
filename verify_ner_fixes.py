"""Verify all four NER fixes."""
from nlp.medical_ner import extract_entities

print("=== Issue 1: dapagliflozin extracted from plan text ===")
e = extract_entities("Plan: Start dapagliflozin 10 mg OD from 12 Feb 2024.")
drugs = [x for x in e if x["entity_type"] == "Drug"]
print(f"Drugs found: {[d['text'] for d in drugs]}")
print("[OK]" if any("dapagliflozin" in d["text"].lower() for d in drugs) else "[FAIL]")

print("\n=== Issue 2: GINA severity classification extracted ===")
e = extract_entities("Assessment: consistent with moderate persistent asthma (GINA classification, step 3).")
diags = [x for x in e if x["entity_type"] == "Diagnosis"]
print(f"Diagnoses found: {[d['text'] for d in diags]}")
print("[OK]" if any("moderate persistent" in d["text"].lower() for d in diags) else "[FAIL]")

print("\n=== Issue 3: paragraph boundary bleed prevented ===")
e = extract_entities("NT-proBNP 4200 pg/mL.\nAllergies: penicillin allergy (rash, 2018).")
conflicts = [x for x in e if x["entity_type"] == "Conflict"]
print(f"Conflicts found: {[c['text'] for c in conflicts]}")
bleed = any("\n" in c["text"] for c in conflicts)
print("[OK] no bleed" if not bleed else "[FAIL] bleed detected")

print("\n=== Issue 4: allergic rhinitis NOT classified as Conflict ===")
e = extract_entities("Past Medical History: seasonal allergic rhinitis. Allergies: NKDA.")
conflicts = [x for x in e if x["entity_type"] == "Conflict" and not x.get("negated")]
texts = [c["text"] for c in conflicts]
print(f"Non-negated conflicts: {texts}")
rhinitis_as_conflict = any("rhinitis" in t.lower() for t in texts)
print("[OK] rhinitis excluded" if not rhinitis_as_conflict else "[FAIL] rhinitis still a conflict")