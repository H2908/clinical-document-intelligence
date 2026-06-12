"""Diagnostic — confirm reproducibility_grounded actually filters ungrounded flags
out of the Jaccard set, not just grades them and forgets to filter."""
import json
from database.snowflake_reader import read_documents_for_patient
from evaluation.grounding import grade_flag, is_grounded
from evaluation.metrics import (
    _split_rule_ai, _flag_set, _mean_pairwise_jaccard,
    reproducibility_grounded, group_runs_by_patient_condition,
)

rows = [json.loads(line) for line in open("evaluation/results/smoke.jsonl", encoding="utf-8")]
docs = read_documents_for_patient("pat_test_01")
doc_text_by_id = {d["document_id"]: d.get("extracted_text", "") for d in docs}

by_pc = group_runs_by_patient_condition(rows)

target = ("pat_test_01", "hybrid_unvalidated")
runs = by_pc[target]

print("=" * 75)
print("CHECKING hybrid_unvalidated FILTER THREADING")
print("=" * 75)
print()

# Manually mirror what reproducibility_grounded does, with full visibility
grounded_sets = []
total_ai_seen = 0
total_grounded_kept = 0
total_ungrounded_filtered = 0

for i, r in enumerate(runs):
    accepted = r.get("accepted_flags", [])
    _rule, ai_flags = _split_rule_ai(accepted)
    print(f"--- Rep {i}: {len(ai_flags)} AI flags ---")
    grounded = []
    for f in ai_flags:
        total_ai_seen += 1
        result = grade_flag(f, doc_text_by_id)
        verdict = result["verdict"]
        keep = is_grounded(verdict)
        desc = (f.get("description") or "")[:60]
        marker = "KEEP " if keep else "DROP "
        print(f"  {marker} verdict={verdict:25s} | {desc}")
        if keep:
            grounded.append(f)
            total_grounded_kept += 1
        else:
            total_ungrounded_filtered += 1
    grounded_sets.append(_flag_set(grounded))
    print(f"  -> {len(grounded)} grounded flags enter Jaccard set for rep {i}")
    print()

# What entered the Jaccard
print("=" * 75)
print("WHAT ENTERED THE JACCARD")
print("=" * 75)
print(f"Total AI flags across {len(runs)} reps:        {total_ai_seen}")
print(f"Grounded flags kept (enter Jaccard):    {total_grounded_kept}")
print(f"Ungrounded flags filtered out:          {total_ungrounded_filtered}")
print(f"Per-rep grounded-set sizes:             {[len(s) for s in grounded_sets]}")
print()

manual_jaccard = _mean_pairwise_jaccard(grounded_sets)
print(f"Manual mean pairwise Jaccard (grounded only): {manual_jaccard}")

api_result = reproducibility_grounded(runs, doc_text_by_id)
print(f"reproducibility_grounded() returned:           {api_result}")
print()

if manual_jaccard == api_result:
    print("MATCH: API matches manual computation. Filter is threaded.")
else:
    print("MISMATCH: API does not equal manual computation. Filter has a hole.")