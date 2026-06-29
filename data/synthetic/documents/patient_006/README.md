# patient_006 - Robert Patel

**Construction date:** 2026-06-28
**Domain:** type 2 diabetes mellitus
**Type:** CONTRADICTION case (planted medication-reconciliation contradiction)

## Patient

- Name: Robert Patel
- DOB: 1964-11-03 (age 59 at first document)
- NHS: 999 600 0006
- Sex: M

## Clinical story

A 59-year-old man with type 2 diabetes (diagnosed 2018), hypertension, and
obesity. Glycaemic control has been deteriorating on metformin monotherapy
over a 24-month window (HbA1c 7.4% -> 8.1% -> 8.6%). GP refers to diabetes
clinic for treatment escalation. Diabetes clinic initiates dapagliflozin 10 mg
OD with detailed counselling. Four months later the GP sees the patient for
a hypertension review and the GP-held medication list does not include
dapagliflozin - and additionally includes gliclazide, which does not appear
in any clinic letter.

## Documents

| Doc | Date | Type | Clinical content |
|---|---|---|---|
| 01 | 14 Nov 2023 | GP Annual Diabetes Review | HbA1c 8.6%, metformin only, refer to diabetes clinic, increase ramipril |
| 02 | 09 Feb 2024 | Diabetes Clinic Letter | HbA1c 8.7%, **initiate dapagliflozin 10 mg OD**, counselling documented |
| 03 | 18 Jun 2024 | GP Hypertension Review | BP good, **medication list omits dapagliflozin, includes gliclazide** |

## The planted contradiction

Doc 02 explicitly initiates **dapagliflozin 10 mg OD from 12 Feb 2024** with
counselling on DKA risk, sick-day rules, and urogenital infection awareness.

Doc 03 (four months later) lists the GP-held medications as:
- Metformin 1 g BD
- Gliclazide 80 mg BD
- Ramipril 10 mg OD
- Atorvastatin 20 mg ON

**Dapagliflozin is absent. Gliclazide is novel.**

This is realistic of how real medication reconciliation fails between
primary and secondary care:
- Specialist initiations don't always reach the GP record
- GP records sometimes accumulate medications without clear initiation events
- Without reconciliation, patients can run out of specialist-initiated drugs
  or be double-prescribed across systems

The contradiction agent should detect the medication-list disagreement as
a HIGH-severity finding. See `gold_contradictions.json`.

## Gold flags (design intent)

See `gold_flags.json` for the structured record.

- HIGH `MEDICATION_RECONCILIATION` on `dapagliflozin` (initiated but missing from GP list)
- MEDIUM `MEDICATION_RECONCILIATION` on `gliclazide` (in GP list but no initiation documented)
- MEDIUM `OVERDUE_FOLLOWUP` on `type 2 diabetes`

## What this tests

- Contradiction agent: asymmetric contradiction detection (presence-vs-absence)
- Contradiction agent: medication-list reconciliation across primary/secondary care
- Flag agent: medication-reconciliation rule firing on dapagliflozin gap
- Flag agent: medication-reconciliation rule firing on gliclazide drift
- Flag agent: overdue-followup rule firing on T2DM with no diabetes-specific
  review since Feb 2024
- Matcher: that `dapagliflozin` and `dapagliflozin 10mg OD` collapse under the
  Path B dose-stripping normalisation
