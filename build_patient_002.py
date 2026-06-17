"""Build patient_002 - T2DM case, false-positive control (no contradiction).

Three documents (GP review, diabetes clinic letter, lab report).
Gold flags recorded at construction. Gold contradictions explicitly empty.
"""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import cm
import json

OUT_DIR = Path("data/synthetic/documents/patient_002")
OUT_DIR.mkdir(parents=True, exist_ok=True)

NAME = "Daniel Ofori"
DOB = "1968-03-22"
NHS = "999 200 0002"
ADDRESS = "27 Oakfield Road, Birmingham, B12 8QR"
SEX = "M"
PATIENT_ID = "patient_002"


def write_pdf(filename: str, body_paragraphs: list[str]) -> Path:
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
    for para in body_paragraphs:
        flowables.append(Paragraph(para, body_style))
        flowables.append(Spacer(1, 4))
    doc.build(flowables)
    return out_path


# ============================================================================
# DOC 1 - GP Annual Diabetes Review, 22 May 2023
# ============================================================================
doc1_body = [
    "<b>Acacia Medical Centre</b>",
    "Date: 22 May 2023",
    "<b>ANNUAL DIABETES REVIEW</b>",
    f"Patient: {NAME}",
    f"DOB: {DOB} (age 55)",
    f"NHS Number: {NHS}",
    f"Address: {ADDRESS}",
    "",
    "<b>Active Medical Conditions:</b>",
    "&bull; Type 2 diabetes mellitus (ICD-10: E11.9) &mdash; diagnosed 2019-11-04",
    "&bull; Hypertension (ICD-10: I10) &mdash; diagnosed 2017-06-12",
    "&bull; Obesity (ICD-10: E66.9) &mdash; BMI 31.2",
    "",
    "<b>Current Medications:</b>",
    "&bull; Metformin 500 mg &mdash; 1 g BD (started 2019-12-01)",
    "&bull; Amlodipine 5 mg &mdash; 5 mg OD (started 2017-07-08)",
    "",
    "<b>Allergies:</b> NKDA &mdash; no known drug allergies recorded.",
    "",
    "<b>Review findings:</b>",
    "Patient attended for annual diabetes review. Reports good adherence with metformin. Reports occasional polyuria and "
    "fatigue. No symptoms of hypoglycaemia. Diet review &mdash; high carbohydrate intake, limited exercise. Foot exam normal, "
    "no neuropathy. Fundoscopy referral arranged. BP 142/86, weight 92 kg, BMI 31.2.",
    "",
    "<b>Recent bloods:</b> HbA1c 8.4% (68 mmol/mol), eGFR 78 mL/min/1.73m&sup2;, total cholesterol 5.2, LDL 3.1, ACR 1.8 mg/mmol.",
    "",
    "<b>Plan:</b>",
    "&bull; HbA1c above target; reinforce lifestyle measures",
    "&bull; Refer to dietitian for weight management",
    "&bull; Continue metformin at current dose",
    "&bull; Repeat HbA1c in 3 months &mdash; if persistently &gt;7.5% consider escalating therapy",
    "&bull; Annual retinal screening due",
]

# ============================================================================
# DOC 2 - Diabetes Clinic Letter, 18 Sep 2023
# ============================================================================
doc2_body = [
    "<b>Birmingham City Hospital &mdash; Diabetes Clinic</b>",
    "Date: 18 Sep 2023",
    "<b>OUTPATIENT CLINIC LETTER</b>",
    f"Patient: {NAME}",
    f"DOB: {DOB} (age 55)",
    f"NHS Number: {NHS}",
    "",
    "Dear Dr Acacia,",
    "",
    "I reviewed Mr Ofori today in the diabetes outpatient clinic, referred for sub-optimal glycaemic control.",
    "",
    "<b>History:</b> Type 2 diabetes diagnosed 2019. Currently on metformin 1 g BD &mdash; tolerated well, no GI side effects. "
    "Reports continued polyuria and nocturia. Has attempted dietary modification with limited success; weight unchanged "
    "since May review. No symptoms suggestive of macrovascular complications.",
    "",
    "<b>Examination:</b> Weight 92 kg, BMI 31.2, BP 144/88. Peripheral pulses preserved. Sensation intact to monofilament.",
    "",
    "<b>Investigations:</b> Repeat HbA1c 8.7% (72 mmol/mol) &mdash; worsened from May despite stated adherence. "
    "eGFR 76, ACR 2.1. Lipids stable.",
    "",
    "<b>Impression:</b> Type 2 diabetes with suboptimal control on metformin monotherapy. Renal function preserved.",
    "",
    "<b>Plan:</b>",
    "&bull; Add gliclazide 40 mg OD &mdash; titrate as required",
    "&bull; Continue metformin 1 g BD",
    "&bull; Reinforce lifestyle measures &mdash; referred to community weight management programme",
    "&bull; Repeat HbA1c, U&amp;E, lipids in 3 months",
    "&bull; Review in clinic at 6 months",
    "",
    "Yours sincerely,",
    "Dr R. Patel, Consultant Diabetologist",
]

# ============================================================================
# DOC 3 - Lab Report, 14 Feb 2024 (parses through lab_parser path)
# ============================================================================
doc3_body = [
    "<b>Birmingham Pathology Services &mdash; Laboratory Report</b>",
    "Date of report: 14 Feb 2024",
    "<b>LABORATORY REPORT</b>",
    f"Patient: {NAME}",
    f"DOB: {DOB}",
    f"NHS Number: {NHS}",
    "Sample type: Venous blood",
    "Sample date: 12 Feb 2024",
    "Requesting clinician: Dr R. Patel (Diabetes Clinic)",
    "",
    "<b>Glycaemic markers:</b>",
    "HbA1c: 9.1 % (76 mmol/mol)  [target &lt;7.0 %]",
    "Random glucose: 12.4 mmol/L  [reference 4.0-7.8]",
    "",
    "<b>Renal function:</b>",
    "Sodium: 139 mmol/L  [135-145]",
    "Potassium: 4.4 mmol/L  [3.5-5.0]",
    "Urea: 5.8 mmol/L  [2.5-7.8]",
    "Creatinine: 88 umol/L  [60-110]",
    "eGFR: 74 mL/min/1.73m&sup2;  [&gt;60]",
    "",
    "<b>Lipid profile:</b>",
    "Total cholesterol: 5.0 mmol/L",
    "LDL cholesterol: 3.0 mmol/L",
    "HDL cholesterol: 1.1 mmol/L",
    "Triglycerides: 1.9 mmol/L",
    "",
    "<b>Urine albumin:</b>",
    "Albumin:creatinine ratio: 2.4 mg/mmol  [&lt;3.0]",
    "",
    "<b>Comment:</b>",
    "Glycaemic control has further deteriorated since previous result (HbA1c 8.7% in September 2023). "
    "Renal function preserved with eGFR 74 mL/min/1.73m&sup2; and ACR within normal range. "
    "Lipid profile acceptable. Recommend clinical review.",
]

# ---- Write PDFs ----
p1 = write_pdf("01_GP_Annual_Diabetes_Review_Ofori_22May2023.pdf", doc1_body)
p2 = write_pdf("02_Diabetes_Clinic_Ofori_18Sep2023.pdf", doc2_body)
p3 = write_pdf("03_Lab_Report_Ofori_14Feb2024.pdf", doc3_body)

# ============================================================================
# GOLD FLAGS
# ============================================================================
gold_flags = {
    "patient_id": PATIENT_ID,
    "patient_name": NAME,
    "patient_dob": DOB,
    "patient_nhs": NHS,
    "construction_date": "2026-06-17",
    "design_principle": (
        "T2DM case with worsening glycaemic control. Three documents chronologically "
        "spread May 2023 - Feb 2024. Documents are deliberately diverse: GP annual "
        "review / diabetes clinic specialist letter / lab report. The lab report "
        "tests the lab_parser code path. Pairwise content-token Jaccard should be "
        "< 0.5. NO planted contradictions - this is the false-positive control."
    ),
    "gold_flags": [
        {
            "category": "OVERDUE_FOLLOWUP",
            "clinical_subject": "type 2 diabetes",
            "severity": "MEDIUM",
            "rationale": (
                "Last clinical entry is doc 03 lab report (14 Feb 2024). If evaluation "
                "runs >90 days later (which it will, given today is mid-2026), the "
                "OVERDUE_FOLLOWUP rule should fire on type 2 diabetes."
            ),
            "expected_source_document": "03_Lab_Report_Ofori_14Feb2024.pdf",
        },
    ],
    "additional_AI_flags_acceptable": [
        "AI_UNDOCUMENTED_TREATMENT for SGLT2 inhibitor (clinically defensible at "
        "HbA1c >8% with eGFR adequate, but requires guideline knowledge not "
        "explicitly in the docs - acceptable if emitted but not in gold set).",
        "AI flag for worsening trend (HbA1c 8.4 -> 8.7 -> 9.1) - acceptable as "
        "evidence-grounded but not a deterministic rule trigger.",
        "AI_INVESTIGATION_NO_RESULT for the 'review in clinic at 6 months' plan "
        "from doc 02 having no documented follow-up - acceptable.",
    ],
    "notes": (
        "patient_002 is the FALSE-POSITIVE CONTROL. The contradiction agent should "
        "return [] for this patient. Any contradiction emitted is a false positive "
        "and should be investigated."
    ),
}

(OUT_DIR / "gold_flags.json").write_text(
    json.dumps(gold_flags, indent=2), encoding="utf-8"
)

# ============================================================================
# GOLD CONTRADICTIONS - explicitly empty
# ============================================================================
gold_contradictions = {
    "patient_id": PATIENT_ID,
    "construction_date": "2026-06-17",
    "gold_contradictions": [],
    "notes": (
        "This patient is the false-positive control for the contradiction agent. "
        "The three documents are deliberately internally consistent - same "
        "demographics, same conditions, same medication progression (metformin -> "
        "+ gliclazide), same allergy status (NKDA), same renal function trend. "
        "Any contradiction the agent emits on this patient is a false positive."
    ),
}

(OUT_DIR / "gold_contradictions.json").write_text(
    json.dumps(gold_contradictions, indent=2), encoding="utf-8"
)

# ============================================================================
# README
# ============================================================================
readme = """# patient_002 - Daniel Ofori

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
"""

(OUT_DIR / "README.md").write_text(readme, encoding="utf-8")

print(f"\nWrote patient_002 to {OUT_DIR}/")
print(f"  {p1.name} ({p1.stat().st_size} bytes)")
print(f"  {p2.name} ({p2.stat().st_size} bytes)")
print(f"  {p3.name} ({p3.stat().st_size} bytes)")
print(f"  gold_flags.json")
print(f"  gold_contradictions.json")
print(f"  README.md")