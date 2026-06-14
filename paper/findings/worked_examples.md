\# Worked examples — backbone of the evaluation narrative



Per supervisor 2026-06-14: three named failure modes of unguarded LLM

flagging, each with a concrete case from real outputs.



\## 1. Composition-fabrication — NYHA case

\[Day 3, fill in from JSONL]

LLM emits a flag whose source\_quote is verbatim but assembled from

sentences that don't actually appear together. v1.3 validator Guard 4

catches this.



\## 2. Paraphrase-reproducibility — penicillin case (Day 5)

Across 5 reps, hybrid\_validated emits the same penicillin-allergy flag

with 5 different prose descriptions but identical subject. Old matcher

counted these as 5 distinct flags; new matcher (category + canonical

clinical\_subject) correctly collapses them to 1. LLM-only baselines

paraphrase the subject too, so even the new matcher leaves them as

5 distinct flags - 0/5 intersection across reps.



\## 3. Category-instability — eGFR case (Day 5, spot-check)

The same clinical issue (cardiology requested eGFR bloods in 4 weeks,

no result documented) surfaces under different LLM-invented categories

across reps of hybrid\_validated:

&#x20; rep0: AI\_UNREVIEWED\_FOLLOWUP

&#x20; rep3: AI\_INVESTIGATION\_NO\_RESULT

The matcher correctly keeps these distinct (different category).

Structural finding: unguarded LLM flagging is non-reproducible on

TWO independent axes — paraphrase of the subject, AND inconsistent

category naming for the same issue. Rule layer cannot do this

because it emits a fixed controlled vocabulary. Evidence for guards

that wasn't obvious before.



\## Held-out watch-items (updated)

1\. Ablation reversal (hybrid\_validated > hybrid\_unvalidated) holds on diverse docs?

2\. Grounding-rate gap holds on diverse docs?

3\. AI-repro magnitude climbs past 0.625 on clean inputs?

4\. llm\_naive grounding rate falls from 0.975 on diverse docs?

5\. NEW (Day 5): Does category-instability in LLM-only/unvalidated conditions

&#x20;  persist on diverse documents? Does it widen the hybrid-vs-baseline

&#x20;  reproducibility gap?



\## Open decision for Bahja meeting

Open vocabulary vs constrained category enum for LLM-emitted flags.

Supervisor lean: (b) measure it, don't fix it - the instability is the

evidence. Defer until after Bahja.

