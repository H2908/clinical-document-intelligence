"""Task 9 — coverage stability check.

Compute distinct-flag-key counts per condition for both JSONLs under the
NEW matcher. Yesterday's smoke.jsonl (pre-clinical_subject) vs today's
smoke_with_subject.jsonl (post-clinical_subject). Same matcher.
"""
import json
from collections import defaultdict
from evaluation.metrics import _flag_key


def cov(path: str) -> dict[str, int]:
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    per = defaultdict(set)
    for r in rows:
        per[r["condition"]].update(_flag_key(f) for f in r.get("accepted_flags", []))
    return {c: len(s) for c, s in per.items()}


old = cov("evaluation/results/smoke.jsonl")
new = cov("evaluation/results/smoke_with_subject.jsonl")

conditions = sorted(set(old) | set(new))
print(f"{'condition':<22} {'old_jsonl':>10} {'new_jsonl':>10} {'delta':>8}")
print("-" * 54)
for c in conditions:
    o = old.get(c, 0)
    n = new.get(c, 0)
    print(f"{c:<22} {o:>10} {n:>10} {n - o:>+8}")