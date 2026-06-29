# patient_009 - Lauren Bennett

**Construction date:** 2026-06-28
**Domain:** asthma (respiratory)
**Type:** CONTRADICTION case (planted severity-classification contradiction)

## Patient

- Name: Lauren Bennett
- DOB: 1991-04-18 (age 32 at first document)
- NHS: 999 900 0009
- Sex: F

## Clinical story

A 32-year-old woman with childhood-onset asthma and allergic rhinitis. GP
annual review (Mar 2024) classifies her asthma as mild intermittent based on
infrequent salbutamol use and a high ACT score. Five months later, after
symptom escalation, the respiratory clinic reclassifies as moderate persistent
based on ACT, PEFR variability, and spirometry, and initiates beclometasone
preventer. Three months after that, she presents to A&E with a viral-triggered
exacerbation - and the A&E discharge summary records her asthma as 'mild' in
the past medical history and labels her beclometasone (which she's been on
for 3 months) as 'started today as new preventer'.

## Documents

| Doc | Date | Type | Clinical content |
|---|---|---|---|
| 01 | 11 Mar 2024 | GP Asthma Annual Review | Mild intermittent, salbutamol PRN, ACT 22/25, PEFR 83% predicted |
| 02 | 22 Aug 2024 | Respiratory Clinic Letter | **Reclassified moderate persistent**, **beclometasone 200 mcg BD initiated**, ACT 15/25, PEFR variability 22%, FEV1 72% |
| 03 | 09 Nov 2024 | A&E Discharge Summary | Moderate exacerbation, **records asthma as mild**, **beclometasone described as 'new today'** |

## The planted contradictions

**Contradiction 1: severity classification.**
Doc 02 explicitly reclassifies the asthma as moderate persistent (GINA step 3)
with comprehensive justification. Doc 03 reverts to 'mild' in the past medical
history without acknowledging the Aug reclassification.

**Contradiction 2: medication history.**
Doc 02 initiates beclometasone 200 mcg BD in Aug 2024. Doc 03 (Nov 2024)
describes beclometasone as 'started today as new preventer', erasing the
3-month established history.

Both are realistic of how A&E records frequently default to the patient's
self-reported severity and inherited medication list rather than cross-checking
recent specialist correspondence. Under-classification leads directly to
under-treatment.

## Gold flags (design intent)

See `gold_flags.json` for the structured record.

- HIGH `CLASSIFICATION_CONFLICT` on `asthma severity`
- HIGH `MEDICATION_HISTORY_ERROR` on `beclometasone`
- MEDIUM `OVERDUE_FOLLOWUP` on `asthma`
- Plus 2 tier-2 acceptable-credit flags (treatment-inadequate-response, PEFR diary)

## What this tests

- Contradiction agent: disease-classification contradictions (distinct from
  medication-reconciliation in patient_006 and allergy-status in patient_001)
- Contradiction agent: 1-vs-2 source asymmetry (specialist claim vs
  primary/emergency claim) - tests that specialist reclassification is
  identified as the authoritative position
- Contradiction agent: same-chart multiple contradictions (severity AND
  medication-history) without conflation
- Flag agent: classification-conflict rule firing on documented severity disagreement
- Flag agent: medication-history-error rule firing on preventer history erasure
- Flag agent: overdue-followup on respiratory follow-up gap
- Matcher: dose-stripped matching (`beclometasone` vs `beclometasone 200 mcg BD`)
  under Path B normalisation
