"""Task 9 (v2) - Guardrail 3 properly.

Compare today's JSONL coverage under TWO matchers:
  - old matcher: (category, description.strip())
  - new matcher: (category, canonical(clinical_subject))

Same data, different matcher. This isolates the matcher's effect.
"""
import json
from collections import defaultdict


def old_key(flag: dict) -> tuple[str, str]:
    return (flag.get("category", ""), flag.get("description", "").strip())


def new_key(flag: dict) -> tuple[str, str]:
    return (
        (flag.get("category") or "").strip(),
        (flag.get("clinical_subject") or "").strip().lower(),
    )


def cov(path: str, key_fn) -> dict[str, int]:
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    per = defaultdict(set)
    for r in rows:
        per[r["condition"]].update(key_fn(f) for f in r.get("accepted_flags", []))
    return {c: len(s) for c, s in per.items()}


path = "evaluation/results/smoke_with_subject.jsonl"
old = cov(path, old_key)
new = cov(path, new_key)

conditions = sorted(set(old) | set(new))
print(f"{'condition':<22} {'old_matcher':>12} {'new_matcher':>12} {'delta':>8}")
print("-" * 58)
for c in conditions:
    o = old.get(c, 0)
    n = new.get(c, 0)
    print(f"{c:<22} {o:>12} {n:>12} {n - o:>+8}")