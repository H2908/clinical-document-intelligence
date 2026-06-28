\# Paper notes — Rules Before Reasoning



AAAI 2027 main track (fallback: ML4H Findings).

Working title: "Rules Before Reasoning: Structured Guards for Reproducible Clinical Document Intelligence."

Abstract deadline: 21 July 2026. Paper deadline: 28 July 2026.



\## Day 1 (2026-06-09) — switches and reservations



\- `FLAG\_AGENT\_MODE` env var with 4 values: `rules\_only`, `llm\_naive`, `llm\_thoughtful`, `hybrid`. Module-level \_client cache deleted.

\- `CONTRADICTION\_VALIDATE\_PROVENANCE` env var (default true). `\_validate\_one\_contradiction` extracted.

\- Both switches verified with mocked-LLM tests.



\## Day 2 (2026-06-10) — three-rung ladder + instrument hardening



\### Three-rung ladder built



\- `llm\_naive` — raw text, plausible-but-unguarded prompt, asks for source\_quote as explainability.

\- `llm\_thoughtful` — same raw text input, careful prompt with verbatim-quote / scope-to-docs / negation discipline. No hard validation.

\- `hybrid v1.1 → v1.2` — entity list + rule flags + raw text, prompt-level discipline AND hard post-validation.



Locked 6-field schema across all three: `severity, category, description, cited\_document\_id, source\_quote, grounding\_status`. Temperature 0.7 on all three, logged per call.



\### First observations (single-document pilot, pat\_test\_01)



\- `llm\_naive`: 8 flags, no validation, descriptions invoke guideline knowledge not present in source text (e.g. "guideline-recommended high-intensity dose of 80mg").

\- `llm\_thoughtful`: 5 flags, prompt-only discipline, mostly grounded quotes.

\- `hybrid v1.1` first run: 5 parsed, 4 rejected by verbatim check (80% provenance hallucination rate on first observation).



\### Instrument flaw caught mid-day



Re-ran hybrid v1.1 for diagnostic logging. Got 0 rejections (vs 4/5 earlier). On inspection: Claude had switched to 1-2 word quotes (`"LVEF"`, `"eGFR"`, `"echocardiogram"`, `"penicillin allergy"`) that trivially substring-match. Goodhart's law: the validator became the target, the model learned the cheapest path.



Both data points (80% and 0%) are void as a measurement. Instrument is the target; it requires hardening before any quantitative result is reported.



\### Instrument v1.2 — Guard set (frozen before 5× run)



Pre-registered in `paper/config/instrument\_v1.json`. Git tag: `paper-instrument-frozen`.



1\. \*\*Guard 1 — phantom citation\*\*: `cited\_document\_id` must appear in the patient's documents.

2\. \*\*Guard 2 — trivial quote\*\* (OR'd predicate verified against 13 dev quotes): `(chars >= 30 AND words >= 6) OR (words >= 3 AND quote\_shares\_subject\_with\_flag)`. Soft branch admits terse-but-grounded instructions like "Repeat echocardiogram in 6 months" without opening the keyword loophole.

3\. \*\*Guard 3 — verbatim\*\*: whitespace-normalised substring match against cited document text; rejections sub-bucketed into case-mismatch / paraphrase-or-boundary / fabrication by word-overlap fraction.

4\. \*\*Guard 4 — irrelevant padding\*\*: quote must share at least one >=4-char clinical subject word with the flag's category+description after stripping `spacy.lang.en.STOP\_WORDS` ∪ `{patient, documented, noted, listed, verify, confirm, doctor}`.



Stopword pool tested against 13 dev quotes from naive + thoughtful runs: no flag has its only subject overlap silently eaten by spaCy's stoplist. Cleared to freeze.



\### Dev / held-out discipline



\- `pat\_test\_01` = development instrument. All guard parameters tuned here.

\- 20 synthetic NHS cases = held out. Instrument frozen before this set is touched.

\- Pre-registration commit: see git tag `paper-instrument-frozen`.



\### Day 2 close — sample flags verified verbatim



Two flags from yesterday's runs, both quote-checked True against `doc\_bf78e73c.extracted\_text`:



\- `llm\_naive`, MEDIUM, `investigation\_not\_followed\_up`: source\_quote = `"Repeat echocardiogram in 6 months"`.

\- `llm\_thoughtful`, MEDIUM, `FOLLOW\_UP\_STATUS\_UNKNOWN`: source\_quote = `"Refer to heart failure nurse for medication titration within 2 weeks"`.



\### Limitation worth stating in the paper



Provenance validation guarantees a flag's quote is verbatim, substantial, and topically relevant to the flag. It does not guarantee the quote clinically justifies the flag. That remains a matter for clinician review. Example: a `missing\_medication` flag for HFrEF that cites the medications-list line. The quote is verbatim, substantial, topically relevant — and yet doesn't ground the "missing" claim, because absence cannot be quoted. This is the precise boundary of what mechanical grounding can do.



\### Day 2 remaining (tomorrow morning)



1\. Hybrid prompt v1.2 with inline good/bad quote example.

2\. 5× run on `pat\_test\_01` with full pre-validation logging.

3\. Bucket the full population across runs into fabricated / paraphrased / boundary / case-mismatch / trivial / irrelevant-padding / phantom-citation.

4\. Send advisor the bucketed table.

## Verdict reference card (pat_test_01 dev examples, 2026-06-10)

Reference for v1.3 verdict labels with one concrete example per label
from the dev runs. For Day 21 analysis on held-out data.

### verbatim
0 observed on pat_test_01 dev. Definition: source_quote appears as an
exact substring in cited document (whitespace-collapsed). Retained for
held-out — Claude rarely quotes exactly at temperature 0.7 but may on
some patients.

### paraphrase (accepted as grounded)
Example: source_quote = "bloods including eGFR in 4 weeks"
Cited doc text: "Routine bloods including U&E;, eGFR in 4 weeks"
Token overlap = 1.00, longest contiguous run >= floor. All content
words present, surface form smoothed (punctuation, line breaks).
Verdict: grounded paraphrase.

### fabrication (partial-drift subtype, observed on dev)
Example: source_quote = "Repeat echocardiogram in 6 months to reassess
LVEF and review heart failure therapy"
Cited doc text: "3. Repeat echocardiogram in 6 months"
Token overlap = 0.78 (7/9 content tokens; "reassess" and "review" are
the additions). First half verbatim, second half invented clinical
reasoning the doc does not contain. Falls below 0.80 threshold by
0.02. Detector fires fabrication. Subtype noted in paper: this is
partial-drift, not wholesale invention.

### composition-fabrication
Example: source_quote = "NYHA class II consistent with heart failure
therapy"
Cited doc text:
  "...symptoms consistent with NYHA class II"
  "...Continue current heart failure therapy"
Token overlap = 1.00 (all content words present in doc), longest
contiguous run = 3 tokens, required >= 4. Quote stitches phrases from
separate document sentences into a claim ("NYHA II consistent with HF
therapy") the doc never makes. Caught by n-gram floor; would have
passed token-overlap alone.

### misattributed
0 observed on pat_test_01 dev (only one source-of-truth document in
practice). Definition: token overlap with cited doc < threshold, but
overlap with some OTHER document in patient corpus >= threshold.
Retained for held-out — relevant when patients have multiple distinct
documents.

# Paper Notes

## 2026-06-28 — Step 9 coverage guardrail, supervisor reading

### Path B is validated in design, awaiting domain-diverse smoke

Zero delta from Path A → Path B on pat_test_01 means this patient's documents
happen not to contain the abbreviation or dose-suffix variants Path B was built
to handle. Not evidence Path B is wrong — evidence pat_test_01 is a weak test
for Path B specifically. When the 18 synthetic patients land, cardiology cases
with ACEi/ARNi therapy and explicit dose documentation will exercise Path B
naturally. Until then: Path B is correct-but-dormant.

### Three honest guardrail checks for the matcher

1. **rules_only invariance.** raw=4, new_spec=4, delta=0. Deterministic single
   rep, no dedup expected, none occurred. Proves the matcher doesn't
   over-collapse when there's nothing to collapse.

2. **Path B no-regression.** delta(new_minimal → new_spec) = 0 across all
   conditions. Proves Path B is a pure extension; the minimal matcher is the
   safe baseline and Path B doesn't corrupt it.

3. **LLM deduplication proportionate.** llm_thoughtful 40 → 24 across 5 reps
   means roughly 5 of 8 per-rep flags are stable, 3 are noise. Implied AI
   reproducibility ≈ 5/8 = 0.625. Consistent with the grounded-flag Jaccard
   computed directly — two estimation methods agree (internal consistency
   check we got for free).

### Secondary finding for the paper: deduplication ratio

The raw→new_spec delta is a meaningful number in its own right, not just a
sanity check. **Deduplication ratio = raw emissions / distinct identities**
per condition. High ratio means the LLM is generating many variants of the
same clinical issue.

Per-condition ratios from the 2026-06-14 smoke:

| condition           | raw | distinct | ratio | reading |
|---------------------|-----|----------|-------|---------|
| rules_only          |   4 |   4      | 1.00  | perfectly stable (deterministic) |
| hybrid_validated    |  31 |   8      | 3.88  | rule flags stable, pulling ratio up |
| hybrid_unvalidated  |  26 |   9      | 2.89  | partial validation tightens |
| llm_naive           |  40 |  31      | 1.29  | over-produces unique noise |
| llm_thoughtful      |  40 |  24      | 1.67  | more variation per flag, less unique noise |

This is the counting-inflation finding quantified per condition. Complements
the primary reproducibility table; do not replace it.

### Raw vs deduplicated — never compare directly

raw emissions counts every flag the LLM produces across all reps. Distinct
identities counts unique (category, clinical_subject) pairs. They are
different things. The (raw - distinct) gap is a deduplication measure, not
a matcher-correctness signal. The original spec sec 10 framing of "±1"
applied to same-matcher across-run stability; restating clearly:

Guardrail 3 (corrected): Path B must not produce coverage drops relative to
Path A on identical data (delta_new_minimal_to_new_spec must be small or
zero). The raw-to-distinct gap is unrelated and is a reproducibility
measurement.