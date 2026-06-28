"""
Four metrics for the AAAI evaluation harness.

All functions take JSONL rows (dicts as written by runner.py) and return
plain numeric or list values suitable for pandas tables.

Metrics (per AAAI plan):
    reproducibility(runs)              -> mean pairwise Jaccard across reps. Range 0-1.
    reproducibility_decomposed(runs)   -> {rule, ai, blended} Jaccards.
    hallucination_rate(run)            -> fraction of flags citing entities not
                                          in the patient's extracted entity set.
    provenance_validity(run)           -> fraction of flags with a real cited
                                          document_id (in patient's docs).
    coverage(run, gold)                -> fraction of gold flags recovered.
    coverage_stratified(run, gold)     -> {overall, high_severity, medium_severity,
                                            low_severity} recall.

Notes:
- "run"  = one JSONL row (one patient x condition x sampling_run tuple).
- "runs" = list of rows for the same (patient, condition) across reps.
- Coverage requires a gold-flag list per patient; for smoke testing on
  pat_test_01 we don't have hand-labelled gold, so the notebook passes
  None and the function returns None.

Supervisor lock (Day 4):
- Gold flag canonical schema: {category, clinical_subject, severity}.
  No quote strings. No source_document_id. Design-intent records only.
- Reproducibility must be reported decomposed (rule vs AI vs blended);
  a blended-only number is dishonest because rule flags are deterministic
  by construction.
- Coverage must be reported stratified by severity; high-severity recall
  is the clinically meaningful number.
"""
import re
from typing import Iterable, Optional

from evaluation.grounding import grade_flag, is_grounded


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Clinical subject normalisation (spec sec 5-6)
# ---------------------------------------------------------------------------

# Curated abbreviation table. Maps spelled-out form -> canonical abbreviation.
# Conservative: unlisted pairs do NOT merge. Add to this table only when a
# pair appears in clinical text often enough to cause distinct-flag inflation.
_ABBREVIATION_TABLE = {
    "ace inhibitor":                          "acei",
    "ace inhibitors":                         "acei",
    "estimated glomerular filtration rate":   "egfr",
    "glycated haemoglobin":                   "hba1c",
    "glycated hemoglobin":                    "hba1c",
    "left ventricular ejection fraction":     "lvef",
    "b-type natriuretic peptide":             "bnp",
    "n-terminal pro-bnp":                     "nt-probnp",
}

# Dose-suffix regex. Requires a unit token, so measurement subjects like
# "eGFR 32" or "LVEF 28%" (no unit) are naturally NOT stripped. Drug
# subjects "Furosemide 80 mg" / "Spironolactone 25 mg OD" are stripped
# to the bare drug name.
_DOSE_SUFFIX_RE = re.compile(
    r"\s+\d+[\d.]*\s*(mg|mcg|g|ml|units?|iu)\b.*$",
    flags=re.IGNORECASE,
)


def normalise_subject(subject: str) -> str:
    """Normalise clinical_subject for identity comparison (spec sec 6).

    Pipeline:
      1. lowercase
      2. strip leading/trailing whitespace
      3. collapse internal whitespace
      4. apply abbreviation table (full form -> canonical abbreviation)
      5. strip dose suffix (drug-type subjects only, discriminated by unit)

    Returns the normalised string used for matcher comparison.
    Empty / None / whitespace-only inputs return empty string.
    """
    if not subject:
        return ""
    s = subject.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = _ABBREVIATION_TABLE.get(s, s)
    s = _DOSE_SUFFIX_RE.sub("", s).strip()
    return s


def _flag_key(flag: dict) -> tuple[str, str]:
    """Canonical identity for a flag for set comparisons.

    Identity = (category, canonical(clinical_subject)).
    canonical(s) = s.strip().lower().

    Two flags are the same iff they have the same category AND the same
    canonical clinical_subject. Severity, source_document_id,
    cited_document_id, and description are all deliberately excluded from
    identity:
      - severity is a label not an identity
      - {source,cited}_document_id can differ for the same clinical issue
        cited in different docs
      - description is paraphrasable; the whole point of clinical_subject
        as a first-class field is to make identity robust to paraphrase.

    Flags missing clinical_subject get an empty-string key. They will
    collapse together into a single "no-subject" bucket, which is the
    correct behaviour for the matcher (and an obvious diagnostic signal
    that the upstream is dropping the field).
    """
    return (
        (flag.get("category") or "").strip(),
        normalise_subject(flag.get("clinical_subject") or ""),
    )


def _flag_set(flags: list[dict]) -> set[tuple[str, str]]:
    return {_flag_key(f) for f in flags if isinstance(f, dict)}


def _is_rule_flag(flag: dict) -> bool:
    """Heuristic: rule flags carry source_document_id; AI flags carry cited_document_id.

    The flag schemas diverge: deterministic rule flags emit source_document_id
    (and no source_quote / grounding_status); v1.3 AI flags emit
    cited_document_id + source_quote + grounding_status. We use the presence
    of cited_document_id as the AI marker.
    """
    return "cited_document_id" not in flag


def _split_rule_ai(flags: list[dict]) -> tuple[list[dict], list[dict]]:
    """Partition a flag list into (rule_flags, ai_flags)."""
    rule, ai = [], []
    for f in flags:
        if not isinstance(f, dict):
            continue
        if _is_rule_flag(f):
            rule.append(f)
        else:
            ai.append(f)
    return rule, ai


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
def _grounded_flags(
    accepted_flags: list[dict],
    doc_text_by_id: dict[str, str],
) -> list[dict]:
    """Return the subset of accepted flags that are grounded under v1.3.

    For each flag, runs evaluation.grounding.grade_flag() and keeps only
    those whose verdict is in {"verbatim", "paraphrase"}. Rule flags
    typically have no source_quote and grade as 'empty-content-quote' →
    excluded. AI flags grade according to Tier 0/1/2 logic.

    NOTE: rule flags are deterministic and reproducible by construction.
    Excluding them from grounded-flag analysis is the right call because
    the grounded-flag metric measures LLM behaviour under provenance
    constraints — rule flags have no provenance to validate.
    """
    out = []
    for f in accepted_flags:
        if not isinstance(f, dict):
            continue
        result = grade_flag(f, doc_text_by_id)
        if is_grounded(result["verdict"]):
            out.append(f)
    return out



def _mean_pairwise_jaccard(sets: list[set]) -> Optional[float]:
    """Mean pairwise Jaccard over a list of sets.

    If every set is empty across all runs, returns None (nothing to measure).
    Otherwise returns the mean of Jaccard scores over all pairs. Two empty
    sets count as 1.0 (they agree there's nothing to flag).
    """
    if all(len(s) == 0 for s in sets):
        return None
    pairs: list[float] = []
    n = len(sets)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = sets[i], sets[j]
            if not a and not b:
                pairs.append(1.0)
                continue
            union = a | b
            if not union:
                pairs.append(1.0)
                continue
            pairs.append(len(a & b) / len(union))
    return sum(pairs) / len(pairs) if pairs else None


# ---------------------------------------------------------------------------
# Metric 1 - Reproducibility (blended Jaccard across reps)
# ---------------------------------------------------------------------------
def reproducibility(runs: list[dict]) -> Optional[float]:
    """Mean pairwise Jaccard similarity across reps of one (patient, condition).

    Returns:
        None  - if fewer than 2 runs provided.
        1.0   - if all reps produced the identical flag set.
        0.0   - if no flag appears in more than one rep.
        else  - mean of pairwise Jaccard over all pairs of reps.

    Jaccard(A, B) = |A & B| / |A | B|. Both empty sets count as 1.0.

    NOTE: This is the blended view (rule + AI flags together). Use
    reproducibility_decomposed() for the honest breakdown.
    """
    if not runs or len(runs) < 2:
        return None
    flag_sets = [_flag_set(r.get("accepted_flags", [])) for r in runs]
    return _mean_pairwise_jaccard(flag_sets)


def reproducibility_decomposed(runs: list[dict]) -> Optional[dict]:
    """Decomposed reproducibility — rule-flag and AI-flag separately, plus blended.

    Returns:
        None if fewer than 2 runs.
        Otherwise:
            {
                "rule":    mean pairwise Jaccard on rule-flag sets,
                "ai":      mean pairwise Jaccard on AI-flag sets,
                "blended": mean pairwise Jaccard on the full flag set
            }
        Any of rule/ai may be None if that flag class doesn't appear in
        the runs (e.g. rules_only has no AI flags; llm_naive has no rules).

    Rationale (supervisor Day 4): a blended Jaccard hides that
    deterministic rule flags reproduce perfectly (1.0) while AI flags vary.
    The decomposed view separates "deterministic layer reproduces by
    construction" from "AI layer reproduces at rate X."
    """
    if not runs or len(runs) < 2:
        return None

    rule_sets = []
    ai_sets   = []
    full_sets = []
    for r in runs:
        rule_flags, ai_flags = _split_rule_ai(r.get("accepted_flags", []))
        rule_sets.append(_flag_set(rule_flags))
        ai_sets.append(_flag_set(ai_flags))
        full_sets.append(_flag_set(r.get("accepted_flags", [])))

    return {
        "rule":    _mean_pairwise_jaccard(rule_sets),
        "ai":      _mean_pairwise_jaccard(ai_sets),
        "blended": _mean_pairwise_jaccard(full_sets),
    }


# ---------------------------------------------------------------------------
# Metric 2 - Hallucination Rate
# ---------------------------------------------------------------------------
def hallucination_rate(run: dict, valid_entity_texts: Optional[set[str]] = None) -> Optional[float]:
    """Fraction of flags citing an entity not in the patient's extracted entity set.

    Args:
        run                 - one JSONL row.
        valid_entity_texts  - optional set of lowercase entity surface forms
                              for the patient. If provided, the metric
                              additionally checks that any 4+ char alpha
                              token in the source_quote appears in the
                              entity set. If None, falls back to the
                              phantom-citation check (cited document ID
                              must exist in the patient's document set).

    Range 0.0 (no hallucinations) to 1.0 (every flag hallucinated).

    Returns None if the run has zero flags (no denominator).

    Held-out watch-item: pass valid_entity_texts on the held-out run so
    the stricter check fires. On pat_test_01 with degenerate (identical)
    input documents, the lax check returned 0 across all conditions.
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

    Framed positively: "what fraction of citations are valid?"
    A flag with no citation at all counts as invalid (denominator non-zero,
    no doc_id to validate against).

    Returns None if the run has zero flags.
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
# Metric 4 - Coverage (overall and severity-stratified)
# ---------------------------------------------------------------------------
def coverage(run: dict, gold_flags: Optional[Iterable[dict]]) -> Optional[float]:
    """Fraction of gold-standard flags recovered by this run.

    Args:
        run         - one JSONL row.
        gold_flags  - iterable of dicts, each carrying:
                        category          (required, str)
                        clinical_subject  (required, str — case-insensitive
                                           substring match against produced
                                           flag's description)
                        severity          (required, "HIGH"|"MEDIUM"|"LOW")
                      No quote strings. No source_document_id. Design-intent
                      records only.
                      If None or empty, returns None.

    Matching rule:
        A gold flag is "recovered" if there exists a produced flag with
        the same category AND (no clinical_subject specified OR the
        clinical_subject substring matches the produced flag's description
        case-insensitively).
        Category+subject match, not quote match. Quotes are for grounding
        analysis, not coverage.
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


def coverage_stratified(
    run: dict,
    gold_flags: Optional[Iterable[dict]],
) -> Optional[dict]:
    """Coverage broken out by severity.

    Returns None if gold_flags is None or empty. Otherwise:
        {
            "overall":         recall over all gold flags,
            "high_severity":   recall over gold flags where severity == "HIGH"
                               (None if no HIGH gold flags),
            "medium_severity": recall over MEDIUM (None if none),
            "low_severity":    recall over LOW (None if none),
        }

    Rationale (supervisor Day 4): a condition that over-produces flags
    (e.g. llm_naive at 8/run) can inflate its overall recall by happening
    to hit gold targets while also producing many fabricated flags.
    Reporting high-severity coverage separately answers the reviewer
    question "is the system recovering the important flags or padding
    recall with trivial ones." High-severity recall is the clinically
    meaningful number; the others are diagnostic.
    """
    if gold_flags is None:
        return None
    gold_list = list(gold_flags)
    if not gold_list:
        return None

    by_severity: dict[str, list[dict]] = {"HIGH": [], "MEDIUM": [], "LOW": []}
    for g in gold_list:
        sev = (g.get("severity") or "").upper()
        if sev in by_severity:
            by_severity[sev].append(g)

    return {
        "overall":         coverage(run, gold_list),
        "high_severity":   coverage(run, by_severity["HIGH"])   if by_severity["HIGH"]   else None,
        "medium_severity": coverage(run, by_severity["MEDIUM"]) if by_severity["MEDIUM"] else None,
        "low_severity":    coverage(run, by_severity["LOW"])    if by_severity["LOW"]    else None,
    }
# ---------------------------------------------------------------------------
# Metric 5 - Grounding rate (per run) and reproducibility on grounded flags
# (supervisor Day 4 Fix 1+2: measure reproducibility over grounded outputs only)
# ---------------------------------------------------------------------------
def grounding_rate(run: dict, doc_text_by_id: dict[str, str]) -> Optional[float]:
    """Fraction of accepted flags in this run that pass v1.3 Guard 3.

    For hybrid_validated, this is ~1.0 by construction (Guard 3 already
    filtered). For hybrid_unvalidated, llm_naive, llm_thoughtful, this is
    the real grounding rate — what fraction of their accepted flags would
    survive v1.3 validation.

    Returns None if the run has no accepted flags (no denominator).

    Note: rule flags are excluded from the denominator and numerator because
    they have no source_quote to grade. Rule flags are deterministic and
    grounded-by-construction; including them in this metric would dilute
    the LLM-behaviour signal.
    """
    accepted = run.get("accepted_flags", [])
    if not accepted:
        return None

    _rule, ai_flags = _split_rule_ai(accepted)
    if not ai_flags:
        return None  # no AI flags to grade

    n_grounded = 0
    for f in ai_flags:
        result = grade_flag(f, doc_text_by_id)
        if is_grounded(result["verdict"]):
            n_grounded += 1
    return n_grounded / len(ai_flags)


def reproducibility_grounded(
    runs: list[dict],
    doc_text_by_id: dict[str, str],
) -> Optional[float]:
    """Mean pairwise Jaccard across reps, on the GROUNDED subset only.

    Per supervisor Day 4: reproducibility must be measured over grounded
    flags, not all flags. A reproducibly-fabricated flag is not a
    reproducible result; it's a reproducible error.

    For each rep, we extract the grounded AI flag subset (via grade_flag),
    then compute pairwise Jaccard across reps on those subsets. Rule flags
    are excluded (they're deterministic; including them masks LLM variance).

    Returns:
        None  if fewer than 2 runs, OR if no rep has any grounded AI flags.
        Otherwise the mean pairwise Jaccard (range 0-1).
    """
    if not runs or len(runs) < 2:
        return None

    grounded_sets: list[set] = []
    for r in runs:
        accepted = r.get("accepted_flags", [])
        _rule, ai_flags = _split_rule_ai(accepted)
        grounded = []
        for f in ai_flags:
            result = grade_flag(f, doc_text_by_id)
            if is_grounded(result["verdict"]):
                grounded.append(f)
        grounded_sets.append(_flag_set(grounded))

    return _mean_pairwise_jaccard(grounded_sets)


def grounding_distribution(
    run: dict,
    doc_text_by_id: dict[str, str],
) -> dict[str, int]:
    """Histogram of v1.3 verdicts across this run's accepted AI flags.

    Returns counts per verdict: verbatim / paraphrase / fabrication /
    composition-fabrication / misattributed / empty-content-quote.
    Useful for the bucket distribution table in the paper.
    """
    counts = {
        "verbatim": 0,
        "paraphrase": 0,
        "fabrication": 0,
        "composition-fabrication": 0,
        "misattributed": 0,
        "empty-content-quote": 0,
    }
    accepted = run.get("accepted_flags", [])
    _rule, ai_flags = _split_rule_ai(accepted)
    for f in ai_flags:
        result = grade_flag(f, doc_text_by_id)
        v = result["verdict"]
        counts[v] = counts.get(v, 0) + 1
    return counts

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
    """Group runs by (patient_id, condition) — useful for reproducibility."""
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

    Returns a dict suitable for one row of a pandas DataFrame, with
    decomposed reproducibility (rule/ai/blended) and a single coverage
    field (notebook produces severity-stratified breakdown separately
    via coverage_stratified()).
    """
    by_patient_condition = group_runs_by_patient_condition(rows)

    repros: list[dict] = []
    halls: list[float] = []
    provs: list[float] = []
    covs: list[float] = []

    for (patient_id, _cond), patient_rows in by_patient_condition.items():
        r_dec = reproducibility_decomposed(patient_rows)
        if r_dec is not None:
            repros.append(r_dec)
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

    def _mean_field(dicts: list[dict], key: str) -> Optional[float]:
        vals = [d[key] for d in dicts if d.get(key) is not None]
        return sum(vals) / len(vals) if vals else None

    return {
        "n_runs":                  len(rows),
        "n_patients":              len({r.get("patient_id") for r in rows}),
        "reproducibility_rule":    _mean_field(repros, "rule"),
        "reproducibility_ai":      _mean_field(repros, "ai"),
        "reproducibility_blended": _mean_field(repros, "blended"),
        "hallucination_rate":      _mean(halls),
        "provenance_validity":     _mean(provs),
        "coverage":                _mean(covs),
    }


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
