\# Flag identity matching rule (v1.0)



\*\*Frozen:\*\* 13 June 2026

\*\*Author:\*\* Harshit Taneja

\*\*Supervisor sign-off:\*\* Day 5 review confirming this approach over B1/B2 (heuristic extraction from description).



\## Motivation



On Day 4 we discovered that strict-string Jaccard on `(category, description)`

was under-counting clinically-identical paraphrases as distinct flags. The

penicillin-allergy flag recurred in all 5 reps of `hybrid\_unvalidated` with

near-identical wording (semicolon vs period), but `\_flag\_key` scored them as

distinct, producing a misleadingly low grounded-reproducibility number (0.07).



Two recovery options were considered and rejected:



\- \*\*B1\*\* — heuristic extraction of clinical subject from description.

&#x20; Rejected: the extraction heuristic would itself be a load-bearing design

&#x20; decision made after seeing the data, with no independent justification.

\- \*\*B2\*\* — first-noun-phrase matching. Rejected: collapses genuinely

&#x20; distinct flags that share a condition word (e.g. "heart failure with no

&#x20; ACEi" and "heart failure follow-up overdue" both lead with "Heart failure"

&#x20; but are different flags).



\## The rule



Each produced flag carries a structured `clinical\_subject` field, emitted by

its producer:



\- \*\*Rule flags\*\* populate `clinical\_subject` deterministically from the rule.

&#x20; - `POSSIBLE\_DUPLICATE\_MEDICATION` → `clinical\_subject = <drug\_name>`

&#x20;   (e.g. "Atorvastatin").

&#x20; - `OVERDUE\_FOLLOWUP` → `clinical\_subject = <condition\_name>`

&#x20;   (e.g. "Ischaemic Heart Disease").

&#x20; - `AI\_ALLERGY\_DRUG\_CONFLICT` (rule branch) → `clinical\_subject = <allergen>`.

\- \*\*LLM flags\*\* (naive / thoughtful / hybrid second-pass) are instructed by

&#x20; prompt to emit `clinical\_subject` as a structured field, separate from the

&#x20; prose description. The producer declares the subject; the analysis layer

&#x20; never parses it from text.



\## Flag identity



Two flags A and B are the same flag iff:



A.category == B.category



AND



canonical(A.clinical\_subject) == canonical(B.clinical\_subject)



where `canonical(s) = s.lower().strip()`. Whitespace and case differences

do not constitute different subjects; that is a clerical normalisation, not

a clinical one.



\## Coverage



Coverage uses the same rule: a gold flag and a produced flag match iff they

share `category` and `canonical(clinical\_subject)`. Coverage was previously

implemented as `category + clinical\_subject substring against description`;

with both sides now carrying `clinical\_subject` as a structured field,

matching becomes field-to-field. \*\*Coverage scores must not change\*\* under

this transition — if they do, the previous coverage implementation was using

a different rule than this spec, and that's a separate bug to chase.



\## Reproducibility



`reproducibility\_grounded` uses the same identity rule. Two grounded flags

across reps that share `(category, canonical(clinical\_subject))` are the

same flag for Jaccard purposes. Paraphrased wording variation in

`description` does not constitute non-reproduction.



\## Out of scope (does NOT change)



\- The v1.3 Guard 3 grounding instrument (frozen at `paper-instrument-v1-3`).

&#x20; Source\_quote, the four guards, verdict logic, thresholds, the n-gram floor,

&#x20; the misattribution sub-rule — none of that is touched by this change.

\- Grounding verdicts are computed on `source\_quote` against cited document

&#x20; text. `clinical\_subject` is read only by the flag-identity matcher.



\## Constraint on this rule



This rule is fixed BEFORE the matcher is implemented and BEFORE the

held-out run. Any change to the rule after the held-out run begins is a

methodology violation. The git commit landing this file must precede the

commit that implements the matcher.



\## Negative tests



Eight hand-constructed flag pairs in `paper/config/flag\_identity\_test\_cases.py`

exercise the rule. The matcher must pass all 8. Four pairs must merge (same

subject, varied wording); four pairs must stay distinct (same category and

condition, different subject). The 4 distinct cases are the load-bearing

ones — a matcher that only ever merges is the failure mode this rule must

not exhibit.

