"""
Four metrics for the AAAI evaluation harness.

All functions take JSONL rows (dicts as written by runner.py) and return
plain numeric or list values suitable for pandas tables.

Metrics (per AAAI plan):
    reproducibility(runs)        -> Jaccard similarity across reps. Range 0-1.
    hallucination_rate(run)      -> fraction of flags citing entities not in
                                    the patient's extracted entity set. Range 0-1.
    provenance_validity(run)     -> fraction of flags with a real cited
                                    document_id (in patient's docs). Range 0-1.
    coverage(run, gold)          -> fraction of gold flags recovered. Range 0-1.

Notes:
- "run" = one JSONL row (one patient x condition x sampling_run tuple).
- "runs" = list of rows for the same (patient, condition) across reps.
- Coverage requires a gold-flag list per patient; for smoke testing on
  pat_test_01 we don't have hand-labelled gold, so the notebook will pass
  None and the function returns None.
"""
from typing import Iterable, Optional


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _flag_key(flag: dict) -> tuple[str, str]:
    """Canonical identity for a flag for set comparisons.

    Two flags are considered the same if they share (category, description).
    Severity / source_document_id deliberately excluded - the same clinical
    issue cited from a different doc is still the same flag.
    """
    return (
        flag.get("category", ""),
        flag.get("description", "").strip(),
    )


def _flag_set(flags: list[dict]) -> set[tuple[str, str]]:
    return {_flag_key(f) for f in flags if isinstance(f, dict)}


def _cited_doc_id(flag: dict) -> Optional[str]:
    """Extract the cited document ID from either field name.

    v1.3 LLM flags use cited_document_id; rule flags + older outputs use
    source_document_id. We accept either.
    """
    return (
        flag.get("cited_document_id")
        or flag.get("source_document_id")
        or None
    )


# ---------------------------------------------------------------------------
# Metric 1 - Reproducibility (Jaccard similarity across reps)
# ---------------------------------------------------------------------------
def reproducibility(runs: list[dict]) -> Optional[float]:
    """Mean pairwise Jaccard similarity across reps of one (patient, condition).

    Returns:
        None  - if fewer than 2 runs are provided (no comparison possible)
        1.0   - if all reps produced the identical flag set (perfect reproducibility)
        0.0   - if no flag appears in more than one rep
        else  - mean of pairwise Jaccard over all pairs of reps

    Jaccard(A, B) = |A & B| / |A | B|  (with the convention 0/0 = 1.0
    when both flag sets are empty - "they agree there's nothing to flag").
    """
    if not runs or len(runs) < 2:
        return None

    flag_sets = [_flag_set(r.get("accepted_flags", [])) for r in runs]

    pair_jaccards: list[float] = []
    n = len(flag_sets)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = flag_sets[i], flag_sets[j]
            if not a and not b:
                pair_jaccards.append(1.0)  # agree on nothing-to-flag
                continue
            union = a | b
            if not union:
                pair_jaccards.append(1.0)
                continue
            pair_jaccards.append(len(a & b) / len(union))

    if not pair_jaccards:
        return None
    return sum(pair_jaccards) / len(pair_jaccards)


# ---------------------------------------------------------------------------
# Metric 2 - Hallucination Rate
# ---------------------------------------------------------------------------
def hallucination_rate(run: dict, valid_entity_texts: Optional[set[str]] = None) -> Optional[float]:
    """Fraction of flags citing an entity not in the patient's extracted entity set.

    Args:
        run                 - one JSONL row
        valid_entity_texts  - set of lowercase entity surface forms for the patient.
                              Optional: if None, falls back to "doc_id not in
                              patient's documents" - the phantom-citation check.

    Range 0.0 (no hallucinations) to 1.0 (every flag hallucinated).

    Returns None if the run has zero flags (no denominator).

    Implementation choice:
      The AAAI plan defines hallucination as "fraction of flags citing an
      entity not present in the extracted entity set." Two reasonable
      operationalisations:
        (a) entity text appears in the flag's source_quote / description
        (b) cited document ID exists in the patient's document set
      We implement (b) as the default because it's deterministic and the
      JSONL rows already carry document_ids. If valid_entity_texts is
      provided, we additionally require any 4+ char alpha token in the quote
      to appear in the entity set.
    """
    flags = run.get("accepted_flags", [])
    if not flags:
        return None

    valid_doc_ids = set(run.get("input", {}).get("document_ids", []))
    n_hallucinated = 0
    n_total = 0

    for f in flags:
        if not isinstance(f, dict):
            continue
        n_total += 1
        cited = _cited_doc_id(f)
        # Phantom citation: cited document doesn't exist in patient's docs
        if cited and cited not in valid_doc_ids:
            n_hallucinated += 1
            continue
        # Optional stronger check: entity-grounding in source_quote
        if valid_entity_texts is not None:
            import re as _re
            quote = (f.get("source_quote") or "").lower()
            tokens = _re.findall(r"[a-z]{4,}", quote)
            if tokens and not any(t in valid_entity_texts for t in tokens):
                n_hallucinated += 1

    if n_total == 0:
        return None
    return n_hallucinated / n_total


# ---------------------------------------------------------------------------
# Metric 3 - Provenance Validity
# ---------------------------------------------------------------------------
def provenance_validity(run: dict) -> Optional[float]:
    """Fraction of flags whose cited_document_id is real (in patient's docs).

    Inverse-ish of hallucination_rate's phantom-citation component, but
    framed positively: "what fraction of citations are valid?"

    Returns None if the run has zero flags (no denominator).

    A flag with no citation at all is counted as invalid (denominator non-zero,
    no doc_id to validate against).
    """
    flags = run.get("accepted_flags", [])
    if not flags:
        return None

    valid_doc_ids = set(run.get("input", {}).get("document_ids", []))
    n_valid = 0
    n_total = 0

    for f in flags:
        if not isinstance(f, dict):
            continue
        n_total += 1
        cited = _cited_doc_id(f)
        if cited and cited in valid_doc_ids:
            n_valid += 1

    if n_total == 0:
        return None
    return n_valid / n_total


# ---------------------------------------------------------------------------
# Metric 4 - Coverage
# ---------------------------------------------------------------------------
def coverage(run: dict, gold_flags: Optional[Iterable[dict]]) -> Optional[float]:
    """Fraction of gold-standard flags recovered by this run.

    Args:
        run         - one JSONL row
        gold_flags  - iterable of dicts, each with at minimum a 'category'
                      key (and optionally 'clinical_subject' or 'description'
                      for finer matching). If None, returns None.

    Returns None if gold_flags is None or empty (no gold = no measurement).

    Matching rule:
        A gold flag is "recovered" if there exists a produced flag with
        the same category AND (no clinical_subject specified OR the
        clinical_subject substring matches the produced flag's description
        case-insensitively).

        This is a category+subject match, not a quote match. Quotes are
        for grounding analysis, not coverage analysis.
    """
    if gold_flags is None:
        return None
    gold_list = list(gold_flags)
    if not gold_list:
        return None

    produced = run.get("accepted_flags", [])
    if not produced:
        return 0.0

    n_recovered = 0
    for gold in gold_list:
        gold_cat = gold.get("category", "")
        gold_subj = (gold.get("clinical_subject") or "").lower()
        for p in produced:
            if not isinstance(p, dict):
                continue
            if p.get("category", "") != gold_cat:
                continue
            if not gold_subj:
                n_recovered += 1
                break
            if gold_subj in (p.get("description") or "").lower():
                n_recovered += 1
                break

    return n_recovered / len(gold_list)


# ---------------------------------------------------------------------------
# Aggregation helpers (used by analysis.ipynb)
# ---------------------------------------------------------------------------
def group_runs_by_condition(rows: list[dict]) -> dict[str, list[dict]]:
    """Group runs by their 'condition' field."""
    out: dict[str, list[dict]] = {}
    for r in rows:
        c = r.get("condition", "unknown")
        out.setdefault(c, []).append(r)
    return out


def group_runs_by_patient_condition(rows: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """Group runs by (patient_id, condition) - useful for reproducibility."""
    out: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        key = (r.get("patient_id", ""), r.get("condition", ""))
        out.setdefault(key, []).append(r)
    return out


def summarise_condition(
    rows: list[dict],
    gold_by_patient: Optional[dict[str, list[dict]]] = None,
) -> dict:
    """Compute all four metrics for a single condition's runs.

    Returns a dict with mean values across patients (where applicable),
    suitable for one row of a pandas DataFrame.
    """
    by_patient_condition = group_runs_by_patient_condition(rows)

    repros: list[float] = []
    halls: list[float] = []
    provs: list[float] = []
    covs: list[float] = []

    for (patient_id, _cond), patient_rows in by_patient_condition.items():
        r = reproducibility(patient_rows)
        if r is not None:
            repros.append(r)
        for row in patient_rows:
            h = hallucination_rate(row)
            if h is not None:
                halls.append(h)
            p = provenance_validity(row)
            if p is not None:
                provs.append(p)
            if gold_by_patient is not None:
                gold = gold_by_patient.get(patient_id)
                c = coverage(row, gold)
                if c is not None:
                    covs.append(c)

    def _mean(xs: list[float]) -> Optional[float]:
        return sum(xs) / len(xs) if xs else None

    return {
        "n_runs":              len(rows),
        "n_patients":          len({r.get("patient_id") for r in rows}),
        "reproducibility":     _mean(repros),
        "hallucination_rate":  _mean(halls),
        "provenance_validity": _mean(provs),
        "coverage":            _mean(covs),
    }