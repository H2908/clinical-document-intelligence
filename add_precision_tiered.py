"""Append precision_tiered to evaluation/metrics.py.

Per supervisor 2026-06-17: tier-2 flags excluded from precision denominator
entirely. Function is additive - touches nothing else in metrics.py.
Aborts if the file already contains 'def precision_tiered' (idempotency).
"""
from pathlib import Path

p = Path("evaluation/metrics.py")
src = p.read_text(encoding="utf-8")

if "def precision_tiered" in src:
    print("[SKIP] precision_tiered already present in metrics.py - nothing to do")
    raise SystemExit(0)

addition = '''


def precision_tiered(
    accepted_flags: list[dict],
    tier_1_subjects: Iterable[tuple[str, str]],
    tier_2_subjects: Iterable[tuple[str, str]],
) -> Optional[dict]:
    """Precision against three-tier gold.

    Args:
        accepted_flags: Flags emitted by a single run (one rep, one condition).
        tier_1_subjects: Set of (category, canonical_clinical_subject) tuples
            from gold_flags.json where tier == 1. Must-catch errors.
        tier_2_subjects: Set of (category, canonical_clinical_subject) tuples
            from gold_flags.json where tier == 2. Clinically correct but
            credit-neutral - neither rewarded nor punished.

    Returns:
        dict with:
          true_positives: emitted flags matching a tier-1 subject
          false_positives: emitted flags matching neither tier (Tier 3, ungrounded
            from the gold standpoint - may still be evidence-grounded, but the
            gold says they aren't a must-catch issue and the clinician hasn't
            marked them as acceptable either)
          tier_2_masked: emitted flags matching a tier-2 subject (excluded
            from precision denominator)
          precision: TP / (TP + FP); None if no flags fall in either TP or FP

    Per supervisor 2026-06-17: option A - tier-2 flags excluded from the
    denominator entirely. Reasoning: penalising a system for emitting a
    clinically-correct guideline-defensible flag is worse than ignoring it.
    The Tier 1 / Tier 2 boundary is a clinical judgement; this function only
    consumes it.

    Identity rule: reuses _flag_key (category, canonical(clinical_subject)).
    Paraphrase-robust by construction.
    """
    tier_1 = {(c.strip(), s.strip().lower()) for c, s in tier_1_subjects}
    tier_2 = {(c.strip(), s.strip().lower()) for c, s in tier_2_subjects}

    tp = fp = masked = 0
    for f in accepted_flags:
        if not isinstance(f, dict):
            continue
        key = _flag_key(f)
        if key in tier_1:
            tp += 1
        elif key in tier_2:
            masked += 1
        else:
            fp += 1

    denom = tp + fp
    precision = (tp / denom) if denom > 0 else None
    return {
        "true_positives": tp,
        "false_positives": fp,
        "tier_2_masked": masked,
        "precision": precision,
    }
'''

p.write_text(src + addition, encoding="utf-8", newline="\n")
print(f"Appended precision_tiered to {p}")
print(f"File now {len(p.read_text(encoding='utf-8').splitlines())} lines")
print(f"precision_tiered occurrences: {p.read_text(encoding='utf-8').count('precision_tiered')}")