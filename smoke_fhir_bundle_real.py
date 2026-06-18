"""Real-data smoke for build_patient_bundle.

Pulls pat_test_01 from Snowflake, builds the FHIR Bundle, inspects the
shape. Does NOT write to mart.fhir_patient_bundle - that's Block 3.

Looking for:
  - Bundle assembles without exception
  - Reasonable resource counts (Patient=1, Conditions in tens,
    Medications in single digits or tens, Observations in tens)
  - No malformed resources (each has resourceType)
  - Dedup actually fired (e.g. heart failure appears once even though
    multiple docs mention it)
"""
from collections import Counter
from clinical_fhir.fhir_builder import build_patient_bundle

bundle = build_patient_bundle("pat_test_01")

print(f"Bundle.resourceType  : {bundle['resourceType']}")
print(f"Bundle.type          : {bundle['type']}")
print(f"Bundle.timestamp     : {bundle.get('timestamp')}")
print(f"Bundle.entry count   : {len(bundle['entry'])}")

# Tally by resource type
counts = Counter(e["resource"]["resourceType"] for e in bundle["entry"])
print("\nResource counts:")
for rt, n in counts.most_common():
    print(f"  {rt:<25} {n}")

# Show a couple of dedup'd resources to verify multi-doc evidence
print("\nSample Conditions (first 5, looking for multi-doc evidence):")
conditions = [e["resource"] for e in bundle["entry"]
              if e["resource"]["resourceType"] == "Condition"]
for c in conditions[:5]:
    text = c["code"].get("text", "?")
    code = (c["code"].get("coding", [{}])[0] or {}).get("code", "-")
    refs = []
    for ev in c.get("evidence", []):
        for d in ev.get("detail", []):
            refs.append(d.get("reference", "?"))
    print(f"  {text!r:<40} icd10={code:<10} evidence_refs={len(refs)}")

print("\nSample Medications (first 5):")
meds = [e["resource"] for e in bundle["entry"]
        if e["resource"]["resourceType"] == "MedicationStatement"]
for m in meds[:5]:
    text = m["medicationCodeableConcept"].get("text", "?")
    code = (m["medicationCodeableConcept"].get("coding", [{}])[0] or {}).get("code", "-")
    primary = m.get("informationSource", {}).get("reference", "-")
    extras = [d.get("reference") for d in m.get("derivedFrom", [])]
    print(f"  {text!r:<25} bnf={code:<10} primary={primary} extras={len(extras)}")

# Spot-check: every entry has resourceType
broken = [i for i, e in enumerate(bundle["entry"])
          if "resourceType" not in e.get("resource", {})]
print(f"\nMalformed entries: {len(broken)}")
if broken:
    print(f"  Indices: {broken[:5]}")