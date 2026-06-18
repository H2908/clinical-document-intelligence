"""Append live-evidence section to paper/findings/worked_examples.md.

Yesterday's entity cleanup ran the hybrid validator across pat_test_01's
9 documents and produced live rejections of all three documented failure
modes. That's real evidence for the paper, captured during a routine
re-process rather than constructed. Adds an 'Evidence captured during
2026-06-17 cleanup' section.
"""
from pathlib import Path

p = Path("paper/findings/worked_examples.md")

new_section = '''

## Evidence captured during 2026-06-17 cleanup (live on real data)

The hybrid validator's three documented failure modes all fired during the entity cleanup pass on `pat_test_01`'s 9 documents on 2026-06-17. These are live LLM rejections during routine re-processing, not constructed examples from Day 5.

### Composition-fabrication

The LLM second-pass on `doc_7f61d513` emitted this quote claiming to come from a single cited document:

> "Chronic heart failure diagnosed 2022-03-14. Current medications: Ramipril, Bisoprolol, Furosemide, Metformin, Atorvastatin."

Token-overlap with the cited document was 1.00 (every word appears somewhere). But the longest contiguous run of matched tokens was 4, below the required 5. The validator's verdict: composition-fabrication. The quote stitched together scattered words that never appear contiguously in the source.

This is one of the named failure modes documented in `PAPER_NOTES.md` lines 165-175 (the NYHA-composition case from Day 3). The mechanism is the same; the new evidence is a different drug-history composition appearing in real production data.

### Fabrication

On `doc_375bbc8a` the second-pass emitted:

> "Repeat echocardiogram in 6 months to reassess LVEF and review heart failure therapy."

Token-overlap with the cited document was 0.78, below the 0.80 threshold for soft acceptance. No other patient document rescued the overlap. Verdict: fabrication.

### Irrelevant-padding

Multiple flags during the cleanup tried to use this quote:

> "Margaret Thompson\\nDOB 1954-08-15"

…as evidence for flags about *different dates of birth across documents*. The quote shares zero clinical subject words with the flag's own description (the flag's subject words were "appear, birth, correct, dates, different, documents, identity, mismatch, multiple"). Verdict: irrelevant-padding. The quote is from the source document but doesn't ground the specific claim.

### Trivial-quote

Repeatedly across the cleanup: `Amlodipine`, `penicillin allergy`, `Echocardiogram`, `Sarah Evans` — single-word or 2-word quotes that don't meet the strict (chars≥30 AND words≥6) or soft (words≥3 AND subject-overlap) thresholds.

### Implication for the paper

These rejections were not surfaced by the held-out evaluation — they're from a routine maintenance operation (entity cleanup after the NER classifier fix). The grounding instrument is not just running on test data; it's gating real production output. **The v1.3 instrument with the cleaned NER is the v1.4 production state.**

One spot-check observation: a single LLM second-pass on `doc_7f61d513` returned non-JSON during the cleanup. Pipeline tolerated it (logged "ignoring second-pass output"), downstream writes succeeded with the rules-only flag set. Real LLM stochasticity, gracefully handled. Worth one sentence in the limitations section.
'''

if p.exists():
    existing = p.read_text(encoding="utf-8")
    if "Evidence captured during 2026-06-17 cleanup" in existing:
        print("[SKIP] live-evidence section already present")
        raise SystemExit(0)
    p.write_text(existing + new_section, encoding="utf-8", newline="\n")
    print(f"OK appended live-evidence section to {p}")
else:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(new_section.lstrip(), encoding="utf-8", newline="\n")
    print(f"OK created {p} with live-evidence section")

print(f"File now {len(p.read_text(encoding='utf-8').splitlines())} lines")