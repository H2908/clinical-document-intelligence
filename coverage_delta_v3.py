"""Task 9 (v3) - Coverage guardrail across three matchers.

Compares accepted-flag distinct counts under THREE matchers on the same
data (evaluation/results/smoke_with_subject.jsonl):

  - old matcher:    (category, description.strip())                  — original baseline
  - new_minimal:    (category, strip().lower() of clinical_subject)  — pre-Path-B
  - new_spec:       (category, normalise_subject(clinical_subject))  — today's spec-compliant

Same data, three matchers. The deltas tell us:
  old -> new_minimal:  effect of switching from description to subject identity
  new_minimal -> new_spec: effect of adding abbreviation table + dose-stripping

Spec sec 10 guardrail 3: flag counts must not change by more than +/- 1
under the new matcher. Material drops indicate over-merging.
"""
import json
from collections import defaultdict
from pathlib import Path

from evaluation.metrics import normalise_subject


def old_key(flag: dict) -> tuple[str, str]:
    return (flag.get("category", ""), flag.get("description", "").strip())


def new_minimal_key(flag: dict) -> tuple[str, str]:
    return (
        (flag.get("category") or "").strip(),
        (flag.get("clinical_subject") or "").strip().lower(),
    )


def new_spec_key(flag: dict) -> tuple[str, str]:
    return (
        (flag.get("category") or "").strip(),
        normalise_subject(flag.get("clinical_subject") or ""),
    )


def cov(path: Path, key_fn) -> dict[str, int]:
    rows = [json.loads(line) for line in path.open(encoding="utf-8")]
    per = defaultdict(set)
    for r in rows:
        per[r["condition"]].update(key_fn(f) for f in r.get("accepted_flags", []))
    return {c: len(s) for c, s in per.items()}


def raw_accepted(path: Path) -> dict[str, int]:
    """Raw accepted_flag count per condition. Pre-deduplication."""
    rows = [json.loads(line) for line in path.open(encoding="utf-8")]
    per = defaultdict(int)
    for r in rows:
        per[r["condition"]] += len(r.get("accepted_flags", []))
    return dict(per)


path = Path("evaluation/results/smoke_with_subject.jsonl")
old = cov(path, old_key)
nm = cov(path, new_minimal_key)
ns = cov(path, new_spec_key)
raw = raw_accepted(path)

conditions = sorted(set(old) | set(nm) | set(ns) | set(raw))

print(f"{'condition':<22} {'raw':>6} {'old_M':>7} {'new_min':>8} {'new_spec':>9} "
      f"{'Δo→nm':>7} {'Δnm→ns':>8}")
print("-" * 76)
for c in conditions:
    r = raw.get(c, 0)
    o = old.get(c, 0)
    m = nm.get(c, 0)
    s = ns.get(c, 0)
    d1 = m - o
    d2 = s - m
    print(f"{c:<22} {r:>6} {o:>7} {m:>8} {s:>9} {d1:>+7} {d2:>+8}")

print()
print("Interpretation:")
print("  raw       — total accepted flags before dedup (matcher-independent)")
print("  old_M     — distinct flags under (category, description) matcher")
print("  new_min   — distinct under (category, lowered-subject)")
print("  new_spec  — distinct under (category, normalise_subject) — today's matcher")
print("  Δo→nm    — effect of switching to clinical_subject identity")
print("  Δnm→ns   — effect of abbreviation table + dose-stripping (Path B)")
print()
print("Guardrail 3 (spec sec 10): |raw - new_spec| should be within +/- 1")
print("(small dedup is expected; large drops indicate over-merging).")