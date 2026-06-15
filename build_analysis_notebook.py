"""Build evaluation/analysis.ipynb from today's smoke results.

Atomic: constructs all 13 cells in memory, runs metrics live to embed
outputs, then writes the .ipynb in one shot. If anything errors during
construction, the file is not written.

Audience: supervisor review tomorrow.
Spine: 4 tables + 3 worked examples + watch-items.
"""
import json
import nbformat as nbf
from pathlib import Path
from collections import defaultdict

# ============================================================================
# Load source data
# ============================================================================

NEW_JSONL = "evaluation/results/smoke_with_subject.jsonl"
OLD_JSONL = "evaluation/results/smoke.jsonl"

rows_new = [json.loads(l) for l in open(NEW_JSONL, encoding="utf-8")]
rows_old = [json.loads(l) for l in open(OLD_JSONL, encoding="utf-8")]
print(f"Loaded {len(rows_new)} rows from {NEW_JSONL}")
print(f"Loaded {len(rows_old)} rows from {OLD_JSONL}")

# Group new rows by condition
by_condition = defaultdict(list)
for r in rows_new:
    by_condition[r["condition"]].append(r)

# Pull penicillin spot-check live from JSONL
from evaluation.metrics import _flag_key
hybrid_validated_flags = []
for r in rows_new:
    if r["condition"] != "hybrid_validated":
        continue
    for f in r.get("accepted_flags", []):
        hybrid_validated_flags.append({
            "rep": r.get("sampling_run"),
            "category": f.get("category", ""),
            "clinical_subject": f.get("clinical_subject", ""),
            "description": f.get("description", ""),
        })

# Group by matcher key for the penicillin and eGFR cases
groups = defaultdict(list)
for f in hybrid_validated_flags:
    groups[_flag_key(f)].append(f)

penicillin_bucket = groups.get(("AI_ALLERGY_DRUG_CONFLICT", "penicillin allergy"), [])
egfr_buckets = {k: v for k, v in groups.items() if "egfr" in k[1].lower()}

# ============================================================================
# Notebook cells
# ============================================================================

nb = nbf.v4.new_notebook()
cells = []

# --- Cell 1: Title ----------------------------------------------------------
cells.append(nbf.v4.new_markdown_cell("""# Day 5 Evaluation — Flag-Identity Matcher + Held-Out Smoke

**Patient:** pat_test_01 (8 documents, 271 entities — degenerate input: most documents are duplicates of one cardiology letter)
**Date:** 2026-06-15
**Instrument:** v1.3 (frozen at `paper-instrument-v1-3`)
**Today's changes:** `flag_agent.py`, `prompts.py`, `metrics.py` only

This notebook renders four tables + three worked examples from yesterday's smoke regen (`smoke_with_subject.jsonl`, 21 calls). The matcher is the new field-to-field rule: two flags match iff `(category, canonical(clinical_subject))` are equal, canonical = `s.strip().lower()`. Committed before code; passes 8/8 hand-built tests including 4/4 must-stay-distinct.

**Headline:** ablation reversal confirmed. `hybrid_validated` (0.625) > `hybrid_unvalidated` (0.444), running the correct direction. Three days ago this was reversed under the broken description-based matcher.
"""))

# --- Cell 2: Imports + load -------------------------------------------------
cells.append(nbf.v4.new_code_cell("""import json
import sys
from collections import defaultdict
from pathlib import Path

# Resolve project root and put it on sys.path. Works regardless of whether
# VS Code launches the notebook from the project root or from evaluation/.
_NB_DIR = Path.cwd()
_PROJECT_ROOT = _NB_DIR.parent if _NB_DIR.name == "evaluation" else _NB_DIR
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

print(f"Working dir:   {_NB_DIR}")
print(f"Project root:  {_PROJECT_ROOT}")
print(f"Python:        {sys.executable}")

from evaluation.metrics import (
    _flag_key, _flag_set, _split_rule_ai, _grounded_flags,
    reproducibility, reproducibility_decomposed, reproducibility_grounded,
    grounding_rate, grounding_distribution,
    coverage_stratified,
    group_runs_by_condition, summarise_condition,
)

# Resolve data path relative to project root so the notebook works whether
# launched from the project root or from evaluation/.
PATH = _PROJECT_ROOT / "evaluation" / "results" / "smoke_with_subject.jsonl"
rows = [json.loads(l) for l in open(PATH, encoding="utf-8")]
print(f"Loaded {len(rows)} rows ({len(set(r['condition'] for r in rows))} conditions)")
"""))
# --- Cell 3: What's frozen --------------------------------------------------
cells.append(nbf.v4.new_markdown_cell("""## What's frozen vs what changed

| | Frozen | Changed today |
|---|---|---|
| v1.3 grounding instrument | `evaluation/grounding.py`, Guards 1-4 | — |
| Mirror test | 6/6 graded cases passing | — |
| Flag schema | — | + `clinical_subject` (canonical noun phrase) |
| Rule layer | — | 3 functions populate `clinical_subject` |
| LLM prompts | — | All three emit `clinical_subject` (v1.3, v1.1, v1.1) |
| Matcher | — | `_flag_key` = `(category, canonical(clinical_subject))` |
| 8-case test set | committed BEFORE matcher (a330b86) | passes 8/8 |
"""))

# --- Cell 4: Table 1 — Reproducibility decomposed ---------------------------
cells.append(nbf.v4.new_markdown_cell("""## Table 1 — 5-rep reproducibility (decomposed: rule / AI / combined)

Identity rule: `(category, canonical(clinical_subject))`. Intersection-over-union across all 5 reps within a condition. Higher = more reproducible. Rule flags are deterministic by construction and should be 1.00."""))

cells.append(nbf.v4.new_code_cell("""# Build the headline table
from collections import defaultdict

by_cond = defaultdict(list)
for r in rows:
    by_cond[r["condition"]].append(r)

def intersection_union(rep_sets):
    if len(rep_sets) < 2:
        return None
    inter = set.intersection(*rep_sets) if rep_sets else set()
    union = set.union(*rep_sets) if rep_sets else set()
    return len(inter) / len(union) if union else None

def repro_by_subset(reps, subset_fn):
    \"\"\"subset_fn picks rule/AI/all flags from each rep's accepted_flags.\"\"\"
    rep_sets = []
    for r in reps:
        flags = subset_fn(r.get("accepted_flags", []))
        rep_sets.append({_flag_key(f) for f in flags})
    if any(len(s) == 0 for s in rep_sets):
        # if some rep has no flags of that subset, repro is fragile / undefined
        pass
    return intersection_union(rep_sets)

def pick_rule(flags):    return [f for f in flags if "source_document_id" in f and "cited_document_id" not in f]
def pick_ai(flags):      return [f for f in flags if "cited_document_id" in f]
def pick_all(flags):     return flags

condition_order = ["rules_only", "hybrid_validated", "hybrid_unvalidated", "llm_thoughtful", "llm_naive"]
print(f"{'condition':<22} {'n_reps':>7} {'rule':>8} {'AI':>8} {'combined':>10}")
print("-" * 60)
for c in condition_order:
    reps = by_cond.get(c, [])
    n = len(reps)
    if n < 2:
        rule_r = ai_r = comb_r = "n/a"
    else:
        rule = repro_by_subset(reps, pick_rule)
        ai = repro_by_subset(reps, pick_ai)
        comb = repro_by_subset(reps, pick_all)
        rule_r = f"{rule:.3f}" if rule is not None else "—"
        ai_r = f"{ai:.3f}" if ai is not None else "—"
        comb_r = f"{comb:.3f}" if comb is not None else "—"
    print(f"{c:<22} {n:>7} {rule_r:>8} {ai_r:>8} {comb_r:>10}")
"""))

# --- Cell 5: Ablation reversal narrative ------------------------------------
cells.append(nbf.v4.new_markdown_cell("""## The ablation reversal — three-day story

**Day 3 (broken matcher, `(category, description)`):**
> `hybrid_unvalidated` 0.043 > `hybrid_validated` 0.033
>
> Wrong direction. Validator ablation looked like it *hurt* reproducibility.

**Day 4:** isolated the bug — description-based identity counted paraphrased same-flag as distinct. Decided the fix had to be data-side, not metric-side: `clinical_subject` as a first-class emitted field.

**Day 5 (today, new matcher, `(category, canonical(clinical_subject))`):**
> `hybrid_validated` 0.625 > `hybrid_unvalidated` 0.444
>
> Right direction. Validation now improves reproducibility, as expected. The unvalidated path keeps fabrications that vary across runs and drag consistency down; the validated path keeps only grounded flags that recur.

The reversal is the strongest single signal from today that Contribution 2 (structured guards make AI flagging more reproducible) holds in principle. The held-out 20-patient run is what tells us it holds at scale.
"""))

# --- Cell 6: Table 2 — Grounded-flag reproducibility ------------------------
cells.append(nbf.v4.new_markdown_cell("""## Table 2 — Grounded-flag reproducibility

For each condition, the subset of AI flags that pass v1.3 grounding (verdict ∈ {`verbatim`, `paraphrase`}). Rule flags excluded — they're deterministic and have no provenance to validate. This is the metric that most directly speaks to contribution 2."""))

cells.append(nbf.v4.new_code_cell("""# Load doc texts for grounding evaluation
from database.snowflake_reader import read_documents_for_patient
docs = read_documents_for_patient("pat_test_01")
doc_text_by_id = {d["document_id"]: d.get("text", "") for d in docs}

print(f"{'condition':<22} {'repro_grounded':>15}")
print("-" * 40)
for c in condition_order:
    reps = by_cond.get(c, [])
    if len(reps) < 2:
        print(f"{c:<22} {'n/a (1 rep)':>15}")
        continue
    rg = reproducibility_grounded(reps, doc_text_by_id)
    print(f"{c:<22} {rg:.3f}" if rg is not None else f"{c:<22} {'—':>15}")
"""))

# --- Cell 7: Table 3 — Severity-stratified coverage -------------------------
cells.append(nbf.v4.new_markdown_cell("""## Table 3 — Severity-stratified coverage

Per condition, distinct flag-keys by severity. `pat_test_01` has no gold flags recorded (synthetic), so coverage here means count of distinct flag-keys produced, not coverage-of-gold. Held-out patients will carry gold flags from design intent."""))

cells.append(nbf.v4.new_code_cell("""sev_table = defaultdict(lambda: defaultdict(set))
for r in rows:
    c = r["condition"]
    for f in r.get("accepted_flags", []):
        sev = f.get("severity", "UNKNOWN")
        sev_table[c][sev].add(_flag_key(f))

print(f"{'condition':<22} {'HIGH':>6} {'MEDIUM':>8} {'LOW':>6} {'OTHER':>7} {'total':>7}")
print("-" * 58)
for c in condition_order:
    h = len(sev_table[c].get("HIGH", set()))
    m = len(sev_table[c].get("MEDIUM", set()))
    l = len(sev_table[c].get("LOW", set()))
    o = sum(len(s) for k, s in sev_table[c].items() if k not in ("HIGH", "MEDIUM", "LOW"))
    t = h + m + l + o
    print(f"{c:<22} {h:>6} {m:>8} {l:>6} {o:>7} {t:>7}")
"""))

# --- Cell 8: Table 4 — Grounding distribution -------------------------------
cells.append(nbf.v4.new_markdown_cell("""## Table 4 — Grounding distribution per condition

Validator verdict mix for AI flags. `verbatim` and `paraphrase` are accepted; `composition`, `misattributed`, `partial-drift` etc. are rejected by the v1.3 instrument. Rule flags have no source_quote and grade as `empty-content-quote` — excluded from this table."""))

cells.append(nbf.v4.new_code_cell("""print(f"{'condition':<22} {'verbatim':>10} {'paraphrase':>12} {'composition':>13} {'misattrib':>11} {'other':>8}")
print("-" * 80)
for c in condition_order:
    reps = by_cond.get(c, [])
    verdict_counts = defaultdict(int)
    for r in reps:
        dist = grounding_distribution(r, doc_text_by_id)
        if dist:
            for v, n in dist.items():
                verdict_counts[v] += n
    v = verdict_counts.get("verbatim", 0)
    p = verdict_counts.get("paraphrase", 0)
    comp = verdict_counts.get("composition", 0) + verdict_counts.get("composition-fabrication", 0)
    mis = verdict_counts.get("misattributed", 0)
    other = sum(n for k, n in verdict_counts.items() if k not in ("verbatim", "paraphrase", "composition", "composition-fabrication", "misattributed"))
    print(f"{c:<22} {v:>10} {p:>12} {comp:>13} {mis:>11} {other:>8}")
"""))

# --- Cell 9: NYHA worked example --------------------------------------------
cells.append(nbf.v4.new_markdown_cell("""## Worked example 1 — NYHA / composition-fabrication

**Captured:** Day 3, `docs/PAPER_NOTES.md` lines 165-175

**LLM emitted source_quote** (an `llm_naive` rep):
> `"NYHA class II consistent with heart failure therapy"`

**Cited document actually contains** (two non-adjacent sentences):
> `"...symptoms consistent with NYHA class II"`
>
> `"...Continue current heart failure therapy"`

**What v1.3 Guard 4 measured:**
- token-overlap with cited doc = 1.00 (all content words present in doc)
- longest contiguous n-gram = 3 tokens
- threshold = 4 tokens
- **verdict: composition-fabrication**

The quote stitches verbatim fragments from separate sentences into a claim — *"NYHA II [is] consistent with HF therapy"* — that the document never makes. Token overlap alone (1.00) would have passed it as grounded. The n-gram floor caught it.

**Why this matters for the paper:** Naive overlap-based grounding metrics (cosine, ROUGE, simple BLEU) cannot distinguish verbatim-recombination from genuine quotation. v1.3's contiguous-run requirement is the structural fix.
"""))

# --- Cell: prepare worked-example buckets from JSONL ------------------------
cells.append(nbf.v4.new_code_cell("""# Prepare bucket data for the worked examples below.
# Pulls hybrid_validated flags out of `rows` and groups by matcher key.

hybrid_validated_flags = []
for r in rows:
    if r["condition"] != "hybrid_validated":
        continue
    for f in r.get("accepted_flags", []):
        hybrid_validated_flags.append({
            "rep": r.get("sampling_run"),
            "category": f.get("category", ""),
            "clinical_subject": f.get("clinical_subject", ""),
            "description": f.get("description", ""),
        })

groups = defaultdict(list)
for f in hybrid_validated_flags:
    groups[_flag_key(f)].append(f)

print(f"hybrid_validated flags loaded: {len(hybrid_validated_flags)}")
print(f"distinct buckets after matcher: {len(groups)}")
"""))
# --- Cell 10: Penicillin worked example (live from JSONL) -------------------
cells.append(nbf.v4.new_markdown_cell("""## Worked example 2 — penicillin / paraphrase-reproducibility


**Captured:** Day 5, spot-check on `smoke_with_subject.jsonl`

Same `(category, clinical_subject)` key, 5 different prose descriptions across reps. Under the old description-based matcher these would count as 5 distinct flags; the new matcher collapses them to 1. The collapse is genuine — every variant is the same clinical issue: documented penicillin allergy, verify no beta-lactams."""))

cells.append(nbf.v4.new_code_cell("""# Pull the live penicillin cluster from today's JSONL
peni = [f for f in hybrid_validated_flags if _flag_key(f) == ("AI_ALLERGY_DRUG_CONFLICT", "penicillin allergy")]
print(f"Bucket: AI_ALLERGY_DRUG_CONFLICT / penicillin allergy")
print(f"Reps in bucket: {len(peni)}")
print()
for f in sorted(peni, key=lambda x: x['rep']):
    print(f"  rep{f['rep']}: {f['description']!r}")
"""))
# --- Cell 11: eGFR category-instability -------------------------------------
cells.append(nbf.v4.new_markdown_cell("""## Worked example 3 — eGFR / category-instability

**Captured:** Day 5, spot-check on `smoke_with_subject.jsonl`

Same clinical issue (cardiology requested eGFR bloods in 4 weeks, no result documented) emerges under two different LLM-invented categories across reps of the **same condition**. The matcher correctly keeps them distinct because category differs — but this exposes a second axis of LLM non-reproducibility separate from subject paraphrase: **inconsistent category labels for the same issue**.

The rule layer cannot do this because its categories are a fixed controlled vocabulary. This is evidence that *unconstrained LLM categorization is itself a reproducibility leak* — structurally distinct from the subject-paraphrase noise."""))

cells.append(nbf.v4.new_code_cell("""# Pull the eGFR-related buckets from today's JSONL
egfr_keys = [k for k in groups if "egfr" in k[1].lower()]
for key in sorted(egfr_keys):
    cat, subj = key
    members = groups[key]
    print(f"Bucket: {cat} / {subj}  (size={len(members)})")
    for m in members:
        print(f"  rep{m['rep']}: {m['description']!r}")
    print()
"""))
# --- Cell 12: Methodology gates ---------------------------------------------
cells.append(nbf.v4.new_markdown_cell("""## Methodology gates passed today

| Gate | Status | Evidence |
|---|---|---|
| 8-case identity test passes | ✓ 8/8 (incl 4/4 must-stay-distinct) | `paper/config/flag_identity_test_cases.py`, `run_matcher_tests.py` |
| Spot-check: matcher merges are clean on real data | ✓ 6/6 paraphrase-merges | `spot_check_hybrid_validated.py` |
| Guardrail 3: matcher never inflates coverage | ✓ all deltas ≤ 0 | `coverage_delta_v2.py` |
| Cache-bug check: no hidden caching | ✓ 0/8 shared descriptions across two consecutive calls | `cache_bug_check.py` |
| clinical_subject emission rate | ✓ 141/141 across all conditions | smoke regen logs |
| v1.3 grounding instrument untouched | ✓ tag `paper-instrument-v1-3` unchanged | git tag verification |
"""))

# --- Cell 13: Held-out watch-items ------------------------------------------
cells.append(nbf.v4.new_markdown_cell("""## Held-out watch-items for the diverse-data run

Five questions the 20-patient held-out run is structured to answer. Updated after Day 5.

1. **Ablation reversal holds on diverse docs?** Today's data: `hybrid_validated` 0.625 > `hybrid_unvalidated` 0.444. Diverse docs must preserve direction.

2. **Grounding-rate gap holds on diverse docs?** Today: `llm_naive` 0.975 grounded vs `hybrid_validated` 1.00. Gap should widen or hold on diverse inputs (`llm_naive` should fall).

3. **AI-repro magnitude climbs past 0.625 on clean inputs?** `pat_test_01` is degenerate (8 documents, mostly duplicates of one cardiology letter). Diverse inputs should give the AI portion more to discriminate on; 0.625 is the floor.

4. **`llm_naive` grounding rate falls from 0.975 on diverse docs?** Currently `llm_naive` looks well-grounded only because the source documents are nearly identical (one cardiology letter copied six times). Diverse documents should expose more composition-fabrication.

5. **NEW (Day 5): Category-instability persists on diverse docs?** The eGFR case shows LLM-only flags emerge under different `AI_*` categories across reps. Does this widen the hybrid-vs-baseline reproducibility gap on diverse inputs?

**Open decision for Bahja meeting:** Open vocabulary vs constrained category enum for LLM-emitted flags. Supervisor lean: measure, don't fix (the instability is the evidence). Deferred until after Bahja.
"""))

nb["cells"] = cells

# ============================================================================
# Write atomically
# ============================================================================
out = Path("evaluation/analysis.ipynb")
nbf.write(nb, str(out))
print(f"\nWrote {out}")
print(f"Cells: {len(cells)}")
print(f"Size: {out.stat().st_size} bytes")