"""Check whether the existing smoke_with_subject.jsonl contains any
ALLERGY_CONFLICT flags. If yes, their clinical_subject was emitted by
the OLD Rule 1 (allergy phrase) and is stale relative to today's fix
(drug name). If zero, the smoke is incidentally still valid for
clinical_subject purposes and regeneration can be deferred.
"""
import json
from pathlib import Path

smoke = Path("evaluation/results/smoke_with_subject.jsonl")
allergy_flags = []

with smoke.open(encoding="utf-8") as f:
    for line in f:
        row = json.loads(line)
        for flag in row.get("accepted_flags", []):
            if flag.get("category") == "ALLERGY_CONFLICT":
                allergy_flags.append({
                    "condition": row.get("condition"),
                    "patient_id": row.get("patient_id"),
                    "subject": flag.get("clinical_subject"),
                    "description": (flag.get("description") or "")[:80],
                })

print(f"ALLERGY_CONFLICT flags in existing smoke: {len(allergy_flags)}")
print()
for f in allergy_flags[:15]:
    print(f"  [{f['condition']:<16}] subject={f['subject']!r}")
    print(f"                    desc={f['description']!r}")
    print()