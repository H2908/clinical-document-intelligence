"""Add condition-name normalisation to _derive_conditions so abbreviation
pairs (COPD / Chronic obstructive pulmonary disease, AFib / Atrial
fibrillation, CVA / stroke, etc.) collapse to one entry instead of
appearing as separate conditions.

This is entity-aggregation-layer normalisation, distinct from and
independent of the AAAI flag-identity matcher (evaluation/metrics.py,
locked, untouched). Safe to modify since AAAI is currently paused and
this only affects worker/document_processor.py, which AAAI's matcher
does not depend on.

Found via MTSamples generalisation check: 'COPD' and 'Chronic obstructive
pulmonary disease' both appeared as separate conditions in the same
document (Pneumonia & COPD - Discharge Summary).
"""
from pathlib import Path

p = Path("worker/document_processor.py")
src = p.read_text(encoding="utf-8")

old = '''def _derive_conditions(entities: list[Entity]) -> list[dict[str, Any]]:
    """
    From non-negated Diagnosis entities, build the conditions[] list.
    Deduplicated by lowercase text.
    """
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for e in entities:
        if e["entity_type"] != "Diagnosis":
            continue
        if e.get("negated"):
            continue
        key = e["text"].lower().strip()
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "name": e["text"],
            "icd10_code": e.get("icd10_code"),
        })
    return out'''

new = '''# Curated condition-name abbreviation table. Maps full-form (lowercase)
# to canonical abbreviation. Conservative: unlisted pairs do NOT merge.
# Mirrors the spirit of evaluation/metrics.py's drug abbreviation table
# but is entirely independent - this is entity-aggregation normalisation,
# not flag-identity matching, and does not touch the locked AAAI matcher.
_CONDITION_ABBREVIATIONS: dict[str, str] = {
    "chronic obstructive pulmonary disease": "copd",
    "atrial fibrillation": "afib",
    "cerebrovascular accident": "cva",
    "myocardial infarction": "mi",
    "congestive heart failure": "chf",
    "chronic kidney disease": "ckd",
    "type 2 diabetes mellitus": "t2dm",
    "type 2 diabetes": "t2dm",
    "deep vein thrombosis": "dvt",
    "pulmonary embolism": "pe",
    "urinary tract infection": "uti",
    "systemic inflammatory response syndrome": "sirs",
    "chronic respiratory failure": "crf",
}


def _normalise_condition_name(name: str) -> str:
    """Normalise a condition name for dedup comparison.
    lowercase -> whitespace collapse -> abbreviation table lookup.
    Unlisted terms return their lowercase-stripped form unchanged."""
    key = " ".join(name.lower().strip().split())
    return _CONDITION_ABBREVIATIONS.get(key, key)


def _derive_conditions(entities: list[Entity]) -> list[dict[str, Any]]:
    """
    From non-negated Diagnosis entities, build the conditions[] list.
    Deduplicated by normalised condition name (abbreviation-aware),
    not raw lowercase text. When two entities collapse to the same
    normalised key, the longer/more-specific original text is kept
    as the display name (e.g. prefer 'Chronic obstructive pulmonary
    disease' over 'COPD' for readability), but only one entry survives.
    """
    best_by_key: dict[str, dict[str, Any]] = {}
    for e in entities:
        if e["entity_type"] != "Diagnosis":
            continue
        if e.get("negated"):
            continue
        raw_text = e["text"].strip()
        norm_key = _normalise_condition_name(raw_text)
        existing = best_by_key.get(norm_key)
        if existing is None or len(raw_text) > len(existing["name"]):
            best_by_key[norm_key] = {
                "name": raw_text,
                "icd10_code": e.get("icd10_code"),
            }
    return list(best_by_key.values())'''

if old not in src:
    print("[FAIL] anchor not found")
    raise SystemExit(1)
src = src.replace(old, new, 1)
p.write_text(src, encoding="utf-8", newline="\n")
print("[OK] condition-name normalisation added to _derive_conditions")

import ast
try:
    ast.parse(src)
    print("[OK] AST valid")
except SyntaxError as e:
    print(f"[FAIL] {e}")
    raise SystemExit(1)