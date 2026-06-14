"""Supervisor gate: spot-check that the 14 -> 8 collapse in hybrid_validated
is genuine paraphrase-merge, not distinct issues wrongly fused.

Pulls all hybrid_validated flags from today's smoke JSONL, groups by
_flag_key, and prints each merged bucket so we can eyeball.
"""
import json
from collections import defaultdict
from evaluation.metrics import _flag_key

PATH = "evaluation/results/smoke_with_subject.jsonl"

# Collect all accepted flags from hybrid_validated rows
all_flags = []
for line in open(PATH, encoding="utf-8"):
    row = json.loads(line)
    if row["condition"] != "hybrid_validated":
        continue
    for f in row.get("accepted_flags", []):
        all_flags.append({
            "sampling_run": row.get("sampling_run"),
            "category": f.get("category", ""),
            "clinical_subject": f.get("clinical_subject", ""),
            "description": f.get("description", ""),
        })

print(f"Total hybrid_validated flags across 5 reps: {len(all_flags)}")
print()

# Group by _flag_key
groups = defaultdict(list)
for f in all_flags:
    groups[_flag_key(f)].append(f)

print(f"Distinct keys after matcher: {len(groups)}")
print(f"Mergers (groups with >1 flag): {sum(1 for v in groups.values() if len(v) > 1)}")
print()

# Print each bucket
for i, (key, members) in enumerate(sorted(groups.items()), 1):
    category, subject = key
    print(f"--- BUCKET {i}: category={category!r}  subject={subject!r}  size={len(members)}")
    for m in members:
        print(f"    rep{m['sampling_run']}: {m['description']!r}")
    print()