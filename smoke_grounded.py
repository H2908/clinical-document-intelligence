"""Smoke test for grounded-flag metrics on pat_test_01's 21-row JSONL."""
import json
from database.snowflake_reader import read_documents_for_patient
from evaluation.metrics import (
    grounding_rate,
    reproducibility_grounded,
    grounding_distribution,
    reproducibility_decomposed,
    group_runs_by_patient_condition,
)

rows = [json.loads(line) for line in open("evaluation/results/smoke.jsonl", encoding="utf-8")]
print("Loaded", len(rows), "rows")
print()

docs = read_documents_for_patient("pat_test_01")
doc_text_by_id = {d["document_id"]: d.get("extracted_text", "") for d in docs}
print("Loaded text for", len(doc_text_by_id), "documents")
print()

by_pc = group_runs_by_patient_condition(rows)

header = "{:22s} {:>2s} {:>14s} {:>12s} {:>18s}".format(
    "condition", "n", "ai_repro_old", "ground_rate", "ai_repro_grounded"
)
print(header)
print("-" * 75)

for (patient, cond), runs_pc in by_pc.items():
    n = len(runs_pc)

    old_dec = reproducibility_decomposed(runs_pc)
    if old_dec and old_dec["ai"] is not None:
        old_ai = "{:.3f}".format(old_dec["ai"])
    else:
        old_ai = "----"

    rates = [grounding_rate(r, doc_text_by_id) for r in runs_pc]
    rates = [x for x in rates if x is not None]
    if rates:
        mean_rate = "{:.3f}".format(sum(rates) / len(rates))
    else:
        mean_rate = "----"

    grounded_repro = reproducibility_grounded(runs_pc, doc_text_by_id)
    if grounded_repro is not None:
        g_repro = "{:.3f}".format(grounded_repro)
    else:
        g_repro = "----"

    print("{:22s} {:>2d} {:>14s} {:>12s} {:>18s}".format(
        cond, n, old_ai, mean_rate, g_repro
    ))

print()
print("Verdict distribution (sum across all runs in condition):")
print("-" * 75)
for (patient, cond), runs_pc in by_pc.items():
    total = {}
    for r in runs_pc:
        dist = grounding_distribution(r, doc_text_by_id)
        for k, v in dist.items():
            total[k] = total.get(k, 0) + v
    nonzero = {k: v for k, v in total.items() if v > 0}
    print("  {:22s} {}".format(cond, nonzero))