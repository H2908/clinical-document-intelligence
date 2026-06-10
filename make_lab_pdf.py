"""Generate a small synthetic lab report PDF for testing the lab_parser pipeline."""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

out_dir = Path("data/synthetic/documents")
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / "Lab_Report_Evans_synthetic.pdf"

c = canvas.Canvas(str(out_path), pagesize=A4)
c.setFont("Helvetica", 11)

lines = [
    "NHS Foundation Trust",
    "Pathology Department",
    "",
    "Patient: Mr Evans     DOB: 1958-03-14     NHS: 123 456 7890",
    "Report Date: 22 May 2026",
    "",
    "LABORATORY RESULTS",
    "",
    "Full Blood Count:",
    "  Haemoglobin: 12.4 g/dL",
    "  WCC: 8.2 x10^9/L",
    "  Platelets: 245 x10^9/L",
    "  MCV: 88 fL",
    "",
    "Urea and Electrolytes:",
    "  Sodium: 138 mmol/L",
    "  Potassium: 4.5 mmol/L",
    "  Creatinine: 142 micromol/L",
    "  Urea: 8.2 mmol/L",
    "  eGFR: 32 mL/min/1.73m2",
    "",
    "Liver Function:",
    "  ALT: 28 U/L",
    "  AST: 32 U/L",
    "  ALP: 95 U/L",
    "  Bilirubin: 14 micromol/L",
    "  Albumin: 38 g/L",
    "",
    "Other:",
    "  HbA1c: 7.8 %",
    "  CRP: <5 mg/L",
    "  Troponin T: 12 ng/L",
    "  TSH: 2.4 mIU/L",
    "  Ferritin: 145 mcg/L",
    "",
    "Comments: Renal function deteriorating, consider review.",
    "",
    "Reported by: Dr K. Mitchell, Clinical Chemistry",
]

y = 27 * cm
for line in lines:
    c.drawString(2 * cm, y, line)
    y -= 0.55 * cm

c.save()
print(f"Wrote {out_path}")