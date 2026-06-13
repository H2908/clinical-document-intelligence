"""Run the briefing extractors in isolation against real CORE data."""
from dotenv import load_dotenv
load_dotenv()

from database.snowflake_reader import read_entities_for_patient, read_documents_for_patient
from agents.briefing_agent import _extract_conditions, _extract_medications, _is_noise

entities = read_entities_for_patient("pat_test_01")
print(f"Loaded {len(entities)} entities for pat_test_01\n")

# What types
from collections import Counter
print("Types:", Counter(e.get("entity_type") for e in entities))
print()

# Run the extractors
conditions = _extract_conditions(entities)
print(f"_extract_conditions returned {len(conditions)} items:")
for c in conditions:
    print(f"  {c}")

print()
medications = _extract_medications(entities)
print(f"_extract_medications returned {len(medications)} items:")
for m in medications:
    print(f"  {m}")

print()
# Diagnostic: what diagnoses get rejected and why
print("=== Reject reasons for each Diagnosis entity ===")
for e in entities:
    if e.get("entity_type") != "Diagnosis":
        continue
    text = (e.get("text") or "").strip()
    if e.get("negated"):
        print(f"  REJECT[negated]      {text!r}")
        continue
    if _is_noise(text):
        print(f"  REJECT[noise]        {text!r}")
        continue
    print(f"  KEEP                 {text!r}")
