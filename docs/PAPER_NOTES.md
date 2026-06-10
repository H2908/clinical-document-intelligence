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

