"""Build patient_006 - T2DM case with planted medication-reconciliation contradiction.

The contradiction: secondary care (diabetes clinic, doc 02) initiates
dapagliflozin 10 mg OD with explicit start date. Primary care (GP review,
doc 03) four months later records the patient's medication list as
metformin and gliclazide only - dapagliflozin is absent. This is a
realistic EHR failure mode: specialist-initiated medications don't
always propagate back to the primary care record.

Three PDFs + gold flags + gold contradictions + README, written atomically.

Convention follows patient_001 / patient_002 exactly.
"""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import cm
import json

OUT_DIR = Path("data/synthetic/documents/patient_006")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---- Shared patient identity ----
NAME = "Robert Patel"
DOB = "1964-11-03"
NHS = "999 600 0006"
ADDRESS = "27 Linden Grove, Birmingham, B14 7HJ"
SEX = "M"
PATIENT_ID = "patient_006"


def write_pdf(filename: str, body_paragraphs: list[str]) -> Path:
    """Write a single-page A4 PDF matching the existing synthetic-doc style."""
    out_path = OUT_DIR / filename
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    body_style = styles["BodyText"]
    body_style.fontSize = 10
    body_style.leading = 13
    flowables = []
    for para_text in body_paragraphs:
        flowables.append(Paragraph(para_text, body_style))
        flowables.append(Spacer(1, 4))
    doc.build(flowables)
    return out_path


# ============================================================================
# DOC 1 - GP Annual Diabetes Review, 14 Nov 2023
# Establishes baseline: T2DM on metformin only, HbA1c 8.6%, recommend
# referral to diabetes clinic for escalation.
# ============================================================================
doc1_body = [
    "<b>Linden Grove Surgery</b>",
    "Date: 14 Nov 2023",
    "<b>ANNUAL DIABETES REVIEW</b>",
    f"Patient: {NAME}",
    f"DOB: {DOB} (age 59)",
    f"NHS Number: {NHS}",
    f"Address: {ADDRESS}",
    "",
    "<b>Active Medical Conditions:</b>",
    "&bull; Type 2 diabetes mellitus (ICD-10: E11.9) &mdash; diagnosed 2018-06-12",
    "&bull; Hypertension (ICD-10: I10) &mdash; diagnosed 2016-02-20",
    "&bull; Obesity (BMI 32) (ICD-10: E66.9)",
    "",
    "<b>Current Medications:</b>",
    "&bull; Metformin 1 g BD &mdash; started 2018-07-01",
    "&bull; Ramipril 5 mg OD &mdash; started 2016-03-15",
    "&bull; Atorvastatin 20 mg ON &mdash; started 2020-04-22",
    "",
    "<b>Allergies:</b> NKDA &mdash; no known drug allergies recorded.",
    "",
    "<b>Examination:</b> BP 142/86, HR 78. Weight 96 kg (BMI 32.4). "
    "Foot examination unremarkable. No peripheral neuropathy detected. "
    "Fundoscopy via retinal screening service: no diabetic retinopathy noted on Sept 2023 screen.",
    "",
    "<b>Investigations (today):</b> HbA1c 8.6% (target &lt;7.0%); eGFR 68 mL/min/1.73m&sup2;; "
    "ACR 2.1 mg/mmol; total cholesterol 4.8, LDL 2.9; ALT 32, AST 28.",
    "",
    "<b>Assessment:</b> Glycaemic control remains suboptimal on metformin monotherapy despite "
    "lifestyle counselling. Mr Patel reports good adherence to metformin. BP at upper end of target. "
    "Renal function stable.",
    "",
    "<b>Plan:</b>",
    "&bull; Refer to diabetes clinic for treatment escalation &mdash; consider second-line agent (SGLT2 inhibitor or DPP-4 inhibitor)",
    "&bull; Continue metformin 1 g BD",
    "&bull; Reinforce lifestyle: weight reduction target 5%, increase activity",
    "&bull; Recheck HbA1c at diabetes clinic appointment",
    "&bull; Increase ramipril to 10 mg OD given persistent BP &gt;140/85",
    "",
    "Dr A. Mehta, GP Partner",
]


# ============================================================================
# DOC 2 - Diabetes Clinic Letter, 09 Feb 2024
# THE TRIGGERING DOCUMENT: clinic initiates dapagliflozin 10 mg OD.
# Letter explicitly addressed to GP. Patient told to start dapagliflozin
# from 12 Feb 2024.
# ============================================================================
doc2_body = [
    "<b>City Hospital Diabetes Centre</b>",
    "Date: 09 Feb 2024",
    "<b>CLINIC LETTER</b>",
    f"Patient: {NAME}",
    f"DOB: {DOB} (age 59)",
    f"NHS Number: {NHS}",
    "",
    "Dear Dr Mehta,",
    "",
    "Thank you for referring Mr Patel for treatment escalation. I reviewed him today in the diabetes clinic.",
    "",
    "<b>History:</b> Type 2 diabetes diagnosed 2018, established on metformin 1 g BD since 2018. "
    "HbA1c trajectory: 7.4% (Nov 2021), 8.1% (Nov 2022), 8.6% (Nov 2023). "
    "Patient reports good adherence; no hypoglycaemic episodes; no GI side effects from metformin.",
    "",
    "<b>Cardiovascular and renal status:</b> Hypertensive on ramipril, target now achieved per GP "
    "increase to 10 mg OD. eGFR 68 (stable). No proteinuria. No known cardiovascular disease.",
    "",
    "<b>Examination:</b> BP 132/78, HR 76. Weight 95 kg (down 1 kg from GP review). "
    "Foot examination: pulses intact, monofilament intact, no ulceration. BMI 32.0.",
    "",
    "<b>Investigations (today):</b> HbA1c 8.7% (worsening), eGFR 65, ACR 2.4 mg/mmol.",
    "",
    "<b>Allergies:</b> NKDA.",
    "",
    "<b>Assessment:</b> Persistently suboptimal glycaemic control on metformin monotherapy. "
    "BMI in obese range. Cardiovascular risk profile and renal function support SGLT2 inhibitor "
    "as second-line agent per NICE NG28 update 2022. Will initiate dapagliflozin.",
    "",
    "<b>Plan:</b>",
    "&bull; <b>Start dapagliflozin 10 mg OD from 12 Feb 2024</b> &mdash; counselled re: DKA risk, "
    "sick-day rules, urogenital infection awareness, importance of hydration",
    "&bull; Continue metformin 1 g BD",
    "&bull; Continue ramipril 10 mg OD",
    "&bull; Repeat HbA1c, U&amp;E, urinalysis in 3 months",
    "&bull; Diabetes clinic follow-up at 6 months",
    "&bull; Patient leaflet on SGLT2 inhibitor side-effects provided",
    "",
    "Yours sincerely,",
    "Dr K. Adeyemi, Consultant Diabetologist",
]


# ============================================================================
# DOC 3 - GP Hypertension Review, 18 Jun 2024
# THE CONTRADICTING DOCUMENT: GP records medication list as
# metformin + ramipril + atorvastatin + GLICLAZIDE. NO MENTION OF
# DAPAGLIFLOZIN. The contradiction: secondary care initiated dapagliflozin
# in Feb 2024; GP record in Jun 2024 does not contain it AND has added
# a different drug (gliclazide) that doesn't appear in any clinic letter.
# This is realistic of medication reconciliation failures.
# ============================================================================
doc3_body = [
    "<b>Linden Grove Surgery</b>",
    "Date: 18 Jun 2024",
    "<b>HYPERTENSION REVIEW</b>",
    f"Patient: {NAME}",
    f"DOB: {DOB} (age 59)",
    f"NHS Number: {NHS}",
    "",
    "<b>Reason for visit:</b> Routine 6-month BP check; patient also reports occasional "
    "dizziness on standing, particularly first thing in the morning.",
    "",
    "<b>Active Medical Conditions:</b>",
    "&bull; Type 2 diabetes mellitus (ICD-10: E11.9)",
    "&bull; Hypertension (ICD-10: I10)",
    "&bull; Obesity (ICD-10: E66.9)",
    "",
    "<b>Current Medications (per practice record):</b>",
    "&bull; Metformin 1 g BD",
    "&bull; Gliclazide 80 mg BD",
    "&bull; Ramipril 10 mg OD",
    "&bull; Atorvastatin 20 mg ON",
    "",
    "<b>Allergies:</b> NKDA.",
    "",
    "<b>Examination:</b> BP supine 128/76, standing 112/68 (postural drop 16 mmHg). "
    "HR 74. Weight 94 kg. No oedema. Capillary glucose today 5.2 mmol/L (fasting).",
    "",
    "<b>Assessment:</b> BP control good. Postural drop with morning dizziness is "
    "suggestive of overtreatment vs intercurrent dehydration. Patient denies recent illness. "
    "Capillary glucose suggests no current hypoglycaemia but morning episodes possible.",
    "",
    "<b>Plan:</b>",
    "&bull; Continue current medications",
    "&bull; Advised increased fluid intake, particularly in warm weather",
    "&bull; Home BP diary for two weeks, return for review",
    "&bull; If postural symptoms persist, consider reducing ramipril",
    "&bull; HbA1c due at next routine review (October)",
    "",
    "Dr A. Mehta, GP Partner",
]


# ============================================================================
# Write all three PDFs
# ============================================================================
pdf1 = write_pdf("01_GP_Diabetes_Review_Patel_14Nov2023.pdf", doc1_body)
pdf2 = write_pdf("02_Diabetes_Clinic_Patel_09Feb2024.pdf", doc2_body)
pdf3 = write_pdf("03_GP_Hypertension_Review_Patel_18Jun2024.pdf", doc3_body)
print(f"PDFs written: {pdf1.name}, {pdf2.name}, {pdf3.name}")


# ============================================================================
# gold_flags.json - construction-time gold standard
# ============================================================================
gold_flags = {
    "patient_id": PATIENT_ID,
    "patient_name": NAME,
    "patient_dob": DOB,
    "patient_nhs": NHS,
    "construction_date": "2026-06-28",
    "schema_version": "v2_three_tier",
    "design_principle": (
        "T2DM case with planted medication-reconciliation contradiction. "
        "Secondary care (diabetes clinic, doc 02) initiates dapagliflozin "
        "10 mg OD with explicit start date 12 Feb 2024. Primary care (doc 03, "
        "Jun 2024) records the medication list without dapagliflozin AND with "
        "gliclazide added (gliclazide does not appear in any clinic letter). "
        "Documents are chronologically distinct (Nov 2023, Feb 2024, Jun 2024) "
        "and from different settings (GP / diabetes clinic / GP), targeting "
        "pairwise content-token Jaccard < 0.5."
    ),
    "tier_definitions": {
        "1_gold_must_catch": "A competent clinician would consider missing this an error.",
        "2_acceptable_credit_neutral": "Clinically correct, guideline-supported, but not an error to omit. Neither a coverage hit nor a precision penalty when emitted.",
        "3_wrong": "Fabrications or ungrounded flags (measured at evaluation time; not pre-recorded)."
    },
    "needs_clinician_validation": True,
    "validation_notes": (
        "Tier 1 vs Tier 2 boundary requires clinical judgement. The boundaries below "
        "are our best construction-time guess. Awaiting clinical review."
    ),
    "gold_flags": [
        {
            "tier": 1,
            "category": "MEDICATION_RECONCILIATION",
            "clinical_subject": "dapagliflozin",
            "severity": "HIGH",
            "rationale": (
                "Doc 02 (diabetes clinic, Feb 2024) explicitly initiates dapagliflozin 10 mg OD "
                "from 12 Feb 2024 with detailed counselling documented. Doc 03 (GP, Jun 2024) "
                "records the medication list with NO mention of dapagliflozin. This is a "
                "medication-reconciliation failure: the GP record does not reflect the "
                "specialist-initiated drug. Missing this is a HIGH-severity safety issue - "
                "DKA risk on SGLT2 inhibitors requires GP awareness, and if the patient runs "
                "out of dapagliflozin without the GP record showing it, repeat prescribing fails."
            ),
            "expected_source_document": "02_Diabetes_Clinic_Patel_09Feb2024.pdf"
        },
        {
            "tier": 1,
            "category": "MEDICATION_RECONCILIATION",
            "clinical_subject": "gliclazide",
            "severity": "MEDIUM",
            "rationale": (
                "Doc 03 (GP, Jun 2024) records gliclazide 80 mg BD in the medication list. "
                "Neither doc 01 (Nov 2023 GP review) nor doc 02 (Feb 2024 diabetes clinic) "
                "documents starting gliclazide. The drug appears in the GP record without "
                "any explicit initiation event in the document set. This is the inverse "
                "reconciliation failure: a drug appearing in primary care without corresponding "
                "specialist initiation, which could indicate (a) a separate consultation not "
                "captured here, (b) a prescribing error, or (c) medication-list drift."
            ),
            "expected_source_document": "03_GP_Hypertension_Review_Patel_18Jun2024.pdf"
        },
        {
            "tier": 1,
            "category": "OVERDUE_FOLLOWUP",
            "clinical_subject": "type 2 diabetes",
            "severity": "MEDIUM",
            "rationale": (
                "Last diabetes-specific review is doc 02 (09 Feb 2024). Doc 03 (Jun 2024) "
                "is a hypertension review and only incidentally addresses diabetes via capillary "
                "glucose. At evaluation time (mid-2026) this is well over the 90-day "
                "OVERDUE_FOLLOWUP threshold for a patient with HbA1c 8.7% on dual therapy."
            ),
            "expected_source_document": "02_Diabetes_Clinic_Patel_09Feb2024.pdf"
        },
        {
            "tier": 2,
            "category": "AI_INVESTIGATION_NO_RESULT",
            "clinical_subject": "hba1c",
            "severity": "MEDIUM",
            "rationale": (
                "Doc 02 plans repeat HbA1c at 3 months. Doc 03 (4 months later) does not record "
                "the result of that planned HbA1c. The 3-month dapagliflozin response is a "
                "load-bearing measurement that should have been recorded. Acceptable for the "
                "system to flag this; acceptable to omit because inference of 'no result' "
                "requires cross-document reasoning."
            ),
            "needs_clinician_validation": True
        },
        {
            "tier": 2,
            "category": "AI_DOSE_CONCERN",
            "clinical_subject": "ramipril",
            "severity": "LOW",
            "rationale": (
                "Doc 03 documents a postural BP drop of 16 mmHg with morning dizziness. "
                "Ramipril was titrated from 5 to 10 mg OD between doc 01 and doc 02. The plan "
                "in doc 03 considers reducing ramipril if symptoms persist - the system flagging "
                "this as a dose-concern observation is clinically supported but lower-priority."
            ),
            "needs_clinician_validation": True
        }
    ]
}

(OUT_DIR / "gold_flags.json").write_text(
    json.dumps(gold_flags, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8"
)
print(f"gold_flags.json written: {len(gold_flags['gold_flags'])} gold flags")


# ============================================================================
# gold_contradictions.json
# ============================================================================
gold_contradictions = {
    "patient_id": PATIENT_ID,
    "construction_date": "2026-06-28",
    "schema_version": "v2_claim_based_matching",
    "match_rule": (
        "A gold contradiction is satisfied if the agent emits a contradiction where one side "
        "cites any document in claim_a_sources and the other side cites any document in "
        "claim_b_sources. The clinical fact is what matters, not which specific document-pair "
        "is cited."
    ),
    "gold_contradictions": [
        {
            "category": "MEDICATION_LIST_RECONCILIATION",
            "severity": "HIGH",
            "claim_a": "patient is on dapagliflozin 10 mg OD (specialist-initiated 12 Feb 2024)",
            "claim_b": "patient's medication list does not include dapagliflozin (Jun 2024 GP record)",
            "claim_a_sources": [
                "02_Diabetes_Clinic_Patel_09Feb2024.pdf"
            ],
            "claim_b_sources": [
                "03_GP_Hypertension_Review_Patel_18Jun2024.pdf"
            ],
            "explanation": (
                "Doc 02 is the explicit initiation event for dapagliflozin with start date, "
                "dose, and counselling all documented. Doc 03, four months later, records the "
                "GP-held medication list without dapagliflozin. The contradiction is a real "
                "EHR failure mode: specialist letters do not always result in primary care "
                "record updates, leading to medication reconciliation failures at the patient-"
                "list level. The agent should detect this as a substantive contradiction "
                "about the patient's current medication regime."
            ),
            "rationale_for_planting": (
                "Tests whether the contradiction agent detects medication-list disagreement "
                "across primary and secondary care - the most common real-world medication "
                "reconciliation failure mode. Unlike patient_001's allergy contradiction "
                "(symmetric NKDA vs allergy), this contradiction is asymmetric: doc 02 "
                "asserts a drug exists; doc 03's silence is the disagreement. Tests the "
                "agent's ability to reason about absence-as-claim."
            )
        }
    ]
}

(OUT_DIR / "gold_contradictions.json").write_text(
    json.dumps(gold_contradictions, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8"
)
print(f"gold_contradictions.json written: {len(gold_contradictions['gold_contradictions'])} contradiction(s)")


# ============================================================================
# README.md
# ============================================================================
readme = """# patient_006 - Robert Patel

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
"""

(OUT_DIR / "README.md").write_text(readme, encoding="utf-8")
print(f"README.md written: {len(readme)} chars")


print()
print("=" * 60)
print(f"patient_006 build complete: {OUT_DIR}")
print("=" * 60)
files = sorted(OUT_DIR.iterdir())
for f in files:
    print(f"  {f.name:<48} {f.stat().st_size:>6} bytes")
