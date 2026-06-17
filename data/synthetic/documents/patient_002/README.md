# patient_002 - Daniel Ofori

**Construction date:** 2026-06-17
**Domain:** type 2 diabetes mellitus
**Type:** FALSE-POSITIVE CONTROL (no contradiction planted)

## Patient

- Name: Daniel Ofori
- DOB: 1968-03-22 (age 55 at first document)
- NHS: 999 200 0002
- Sex: M

## Clinical story

A 55-year-old man with type 2 diabetes (dx 2019), hypertension, and obesity.
Glycaemic control has been deteriorating over a 9-month window despite
metformin monotherapy. GP annual review (May 2023) showed HbA1c 8.4% and
recommended escalation if persistent. Diabetes clinic (Sep 2023) showed
HbA1c 8.7% and added gliclazide. Follow-up lab (Feb 2024) shows HbA1c 9.1%
- worsening despite dual therapy. The chart contains a real clinical signal
(uncontrolled diabetes, possibly needing further escalation) but no internal
disagreement.

## Documents

| Doc | Date | Type | Clinical content |
|---|---|---|---|
| 01 | 22 May 2023 | GP Annual Diabetes Review | HbA1c 8.4%, eGFR 78, metformin only, recommend lifestyle + recheck |
| 02 | 18 Sep 2023 | Diabetes Clinic Letter | HbA1c 8.7%, add gliclazide, review at 6 months |
| 03 | 14 Feb 2024 | Lab Report | HbA1c 9.1%, eGFR 74, no further action documented |

## Why this is the false-positive control

- All three documents agree on demographics (age 55, NHS, DOB)
- All three documents agree on allergy status (NKDA)
- Medication progression is consistent and additive (metformin -> + gliclazide)
- Trend in HbA1c is monotonic worsening (8.4 -> 8.7 -> 9.1) - not contradictory
- Renal function is stable (eGFR 78 -> 76 -> 74) - not contradictory

If the contradiction agent emits ANY contradiction on this patient, it is a
false positive and should be investigated. See `gold_contradictions.json`
(explicitly empty list).

## Gold flags (design intent)

See `gold_flags.json` for the structured record.

- MEDIUM `OVERDUE_FOLLOWUP` on `type 2 diabetes`

The system MAY also emit acceptable AI flags around:
- Undocumented treatment intensification (SGLT2 inhibitor)
- Worsening trend across the three timepoints
- No follow-up after the Feb 2024 lab

These are evidence-grounded and acceptable but not in the gold set because
they require guideline knowledge beyond what is explicitly stated in the
documents.

## What this tests

- Contradiction agent: false-positive rate (should be 0 contradictions)
- Lab parser code path: doc 03 is a lab report; lab_parser should extract
  HbA1c, eGFR, lipid panel, and ACR observations
- Flag agent: overdue-followup rule firing on type 2 diabetes
- Combined: that the system can produce sensible clinical flags WITHOUT
  inventing contradictions on a chart that does not contain any
