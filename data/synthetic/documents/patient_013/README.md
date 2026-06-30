# patient_013 - Christopher Walsh

**Construction date:** 2026-06-29
**Domain:** chronic kidney disease (CKD)
**Type:** CONTRADICTION case (planted staging-classification contradiction)

## Patient

- Name: Christopher Walsh
- DOB: 1959-09-27 (age 64 at first document)
- NHS: 999 130 0013
- Sex: M

## Clinical story

A 64-year-old man with established CKD on a background of type 2 diabetes
and long-standing hypertension - the most common UK CKD aetiology profile.
GP annual review (Jan 2024) records CKD stage 3a with eGFR 52, stable
trajectory, treated with ramipril and standard cardiovascular risk
management. Renal clinic (May 2024) measures eGFR 28 and reclassifies as
CKD stage 4 with comprehensive management changes: vaccination programme,
metformin hold, dietetics referral, anaemia workup, vascular access
discussion. GP locum (Oct 2024) records CKD stage 3a again with eGFR 35,
metformin still active, no reference to the renal clinic plan.

## Documents

| Doc | Date | Type | Clinical content |
|---|---|---|---|
| 01 | 16 Jan 2024 | GP CKD Annual Review | **CKD stage 3a**, eGFR 52, ramipril 10 mg OD, stable trajectory |
| 02 | 14 May 2024 | Renal Clinic Letter | **eGFR 28, reclassified CKD stage 4**, hold metformin, dietetics referral, vaccinations, vascular access discussion |
| 03 | 22 Oct 2024 | GP Locum Consultation | **CKD stage 3a** again, **eGFR 35**, metformin still on list, no reference to renal clinic plan |

## The planted contradictions

**Contradiction 1: stage classification.**
Doc 02 reclassifies as CKD stage 4 (eGFR 28) with full justification.
Doc 03 records CKD stage 3a, ignoring the specialist reclassification.
Doc 01's stage 3a is historically defensible; doc 03's stage 3a is the error.

**Contradiction 2: eGFR investigation value.**
Doc 02 records eGFR 28. Doc 03 records eGFR 35 five months later with no
documented intervention. Implausible improvement; likely measurement,
equation, or transcription discrepancy. Either way, clinically meaningful.

Realistic of how locum GPs and rotational staff fail to incorporate
specialist reclassifications - the patient's primary care chart accumulates
outdated stage tags even after the renal team has moved them to a different
management pathway. The downstream cost is real: stage 4 patients need
vaccination, vascular access planning, dietetics input, and metformin
contraindication review. Recording stage 3a means none of those happen.

## Gold flags (design intent)

See `gold_flags.json` for the structured record.

- HIGH `CLASSIFICATION_CONFLICT` on `ckd stage`
- HIGH `INVESTIGATION_VALUE_CONFLICT` on `egfr`
- HIGH `MEDICATION_RECONCILIATION` on `metformin` (hold instruction not actioned)
- MEDIUM `OVERDUE_FOLLOWUP` on `chronic kidney disease`
- Plus 1 tier-2 acceptable-credit flag on anaemia-of-CKD inadequate response

## What this tests

- Contradiction agent: lab-value-anchored classification contradictions
  (distinct from patient_009's narrative-text severity contradiction)
- Contradiction agent: 1-vs-2 source split (specialist single doc vs two
  primary care docs); tests that the agent identifies the specialist as
  authoritative when its position is clinically and quantitatively justified
- Contradiction agent: measurement-value contradictions where the numbers
  themselves are the disagreement (eGFR 28 vs eGFR 35)
- Flag agent: classification-conflict rule firing on CKD stage disagreement
- Flag agent: investigation-value-conflict rule firing on eGFR disagreement
- Flag agent: medication-reconciliation rule firing on metformin hold
  instruction not actioned
- **Matcher: Path B measurement-value preservation** - the matcher must
  NOT collapse `egfr 28` and `egfr 35` into a single `egfr` identity.
  The dose-stripping regex requires a unit token (mg/mcg/g/ml/units/iu)
  which eGFR lacks, so the values are preserved naturally. If this
  preservation fails (e.g., a future matcher change), the contradiction
  becomes invisible at evaluation time.
