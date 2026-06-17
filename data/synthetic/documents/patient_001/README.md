# patient_001 — Margaret Thompson

**Construction date:** 2026-06-17
**Domain:** cardiology + chronic kidney disease
**Type:** CONTRADICTION case (planted allergy contradiction)

## Patient

- Name: Margaret Thompson
- DOB: 1954-08-15 (age 69 at first document)
- NHS: 999 100 0001
- Sex: F

## Clinical story

A 69-year-old woman with chronic heart failure with reduced ejection fraction
(HFrEF, LVEF 28%), CKD stage 3b (eGFR 32), hypertension, and type 2 diabetes.
Presents in early 2024 with worsening exertional dyspnoea; referred from GP
to cardiology; reviewed by cardiology who optimises HF therapy; subsequently
admitted to A&E with acute decompensated heart failure approximately 5 weeks
after the cardiology review.

## Documents

| Doc | Date | Type | Clinical content |
|---|---|---|---|
| 01 | 12 Jan 2024 | GP Referral Letter | Conditions list, current meds, NKDA, referral reason |
| 02 | 28 Feb 2024 | Cardiology Clinic Letter | Echo confirms LVEF 28%, optimise HF therapy, **penicillin allergy** documented |
| 03 | 04 Apr 2024 | A&E Discharge Summary | Acute HF decompensation, hospitalisation, NKDA (reproduces error) |

## The planted contradiction

Doc 01 says **NKDA**.
Doc 02 says **penicillin allergy (rash, 2018), avoid beta-lactams**.
Doc 03 says **NKDA** (the error propagates).

This is realistic of how real EHRs behave: allergy records diverge across primary
and specialist care, and bad records propagate. The contradiction agent should
detect this as a HIGH-severity allergy disagreement. See `gold_contradictions.json`.

## Gold flags (design intent)

See `gold_flags.json` for the structured record.

- HIGH `ALLERGY_CONFLICT` on `penicillin allergy`
- MEDIUM `OVERDUE_FOLLOWUP` on `chronic kidney disease`
- MEDIUM `OVERDUE_FOLLOWUP` on `heart failure`

## What this tests

- Contradiction agent: HIGH-severity allergy contradiction detection
- Flag agent: allergy-conflict rule firing on documented allergy
- Flag agent: overdue-followup rule firing on chronic conditions
- Matcher: that the same allergy contradiction recorded across multiple documents
  collapses correctly rather than counting as multiple separate contradictions
