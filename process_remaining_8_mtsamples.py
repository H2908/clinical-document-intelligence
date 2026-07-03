"""Process the remaining 8 MTSamples documents (Option B scope):
NER extraction, rules_only flags, and a single hybrid_validated pass
per document (no 5-rep ablation - that claim is already established
on the first 2 documents + pat_test_01).

Extends the generalisation-check breadth from 2 to 10 real, non-synthetic
clinical documents. Uses the Guard 3 - fixed pipeline (tokenizer +
threshold fix, validated against 5 regression cases).
"""
import csv
import json
import logging
import re
import time
from datetime import date
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import cm

from dotenv import load_dotenv
load_dotenv()

from worker.document_processor import process_document
from agents.flag_agent import detect_flags


class VerdictCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []
        self._pending = {}

    def emit(self, record):
        msg = record.getMessage()
        if msg.startswith("HYBRID VALIDATOR REJECTION on doc"):
            self._pending = {"document_id": msg.split("doc ")[-1].strip()}
        elif msg.startswith("LLM quote:"):
            self._pending["quote"] = msg.split("LLM quote:", 1)[1].strip().strip("'")
        elif msg.startswith("LLM description:"):
            self._pending["description"] = msg.split("LLM description:", 1)[1].strip().strip("'")
        elif msg.startswith("VERDICT:"):
            self._pending["verdict_raw"] = msg
            m = re.match(r"VERDICT:\s*([a-z-]+)", msg)
            self._pending["verdict"] = m.group(1) if m else "unknown"
            self.records.append(dict(self._pending))
            self._pending = {}


capture = VerdictCapture()
capture.setLevel(logging.WARNING)
flag_logger = logging.getLogger("agents.flag_agent")
flag_logger.addHandler(capture)
flag_logger.propagate = False


OUT_DIR = Path("data/mtsamples/pdfs")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGETS = {
    "multiple_medical_problems": (" Multiple Medical Problems - Discharge Summary ", "discharge_summary"),
    "peripheral_vascular_disease": (" Discharge Summary - Peripheral vascular disease ", "discharge_summary"),
    "discharge_summary_18": (" Discharge Summary - 18 ", "discharge_summary"),
    "er_chest_pain_fever": (" ER Report - Chest Pain & Fever ", "discharge_summary"),
    "neurologic_consultation_5": (" Neurologic Consultation - 5 ", "clinic_letter"),
    "psych_consult_lethargy": (" Psych Consult - Lethargy ", "clinic_letter"),
    "pain_management_consult_1": (" Pain Management Consult - 1 ", "clinic_letter"),
    "huntingtons_disease_consult": (" Huntington's Disease - Consult ", "clinic_letter"),
}

with open("data/mtsamples/mtsamples.csv", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)


def write_pdf(filename: str, text: str, title: str) -> Path:
    out_path = OUT_DIR / filename
    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
    )
    styles = getSampleStyleSheet()
    body_style = styles["BodyText"]
    body_style.fontSize = 10
    body_style.leading = 13
    flowables = [Paragraph(f"<b>{title}</b>", styles["Heading2"]), Spacer(1, 8)]
    paragraphs = text.replace(",", "\n").split("\n")
    for para in paragraphs:
        para = para.strip()
        if para:
            para_safe = para.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            flowables.append(Paragraph(para_safe, body_style))
            flowables.append(Spacer(1, 3))
    doc.build(flowables)
    return out_path


results = {}

for key, (sample_name, doc_type) in TARGETS.items():
    row = next((r for r in rows if r.get("sample_name") == sample_name), None)
    if row is None:
        print(f"[FAIL] could not find sample_name={sample_name!r}")
        continue

    print(f"\n{'='*60}")
    print(f"Processing: {key}")
    print(f"Source: {sample_name.strip()}")
    print(f"{'='*60}")

    pdf_path = write_pdf(f"{key}.pdf", row["transcription"], sample_name.strip())
    print(f"  PDF written: {pdf_path.stat().st_size} bytes")

    t0 = time.time()
    doc_result = process_document(
        file_path=pdf_path,
        document_id=f"mtsamples_{key}",
        patient_id="mtsamples_generalisation_check",
        document_date=date.today(),
        doc_type=doc_type,
    )
    ner_wall = time.time() - t0

    entities = doc_result.get("entities", [])
    for e in entities:
        e["document_id"] = f"mtsamples_{key}"
    conditions = doc_result.get("conditions", [])
    medications = doc_result.get("medications", [])
    observations = doc_result.get("observations", [])

    print(f"  NER wall clock: {ner_wall:.2f}s")
    print(f"  Entities: {len(entities)}  Conditions: {len(conditions)}  "
          f"Medications: {len(medications)}  Observations: {len(observations)}")

    documents_for_flags = [{
        "document_id": f"mtsamples_{key}",
        "document_date": date.today().isoformat(),
        "extracted_text": doc_result["document"].get("extracted_text", ""),
    }]

    # rules_only flags
    rules_flags, _ = detect_flags(
        "mtsamples_generalisation_check", entities, documents_for_flags, mode="rules_only"
    )
    print(f"  Rules-only flags: {len(rules_flags)}")

    # single hybrid_validated pass
    capture.records = []
    t0 = time.time()
    hybrid_flags, hybrid_meta = detect_flags(
        "mtsamples_generalisation_check", entities, documents_for_flags, mode="hybrid"
    )
    hybrid_wall = time.time() - t0
    rejections = list(capture.records)

    for f in hybrid_flags:
        for k, v in f.items():
            if hasattr(v, "isoformat"):
                f[k] = v.isoformat()

    print(f"  Hybrid wall clock: {hybrid_wall:.2f}s")
    print(f"  Hybrid accepted: {len(hybrid_flags)}  Hybrid rejected: {len(rejections)}")
    for hf in hybrid_flags:
        print(f"    ACCEPTED [{hf.get('severity')}] {hf.get('clinical_subject')}: {hf.get('source_quote')!r}")
    for r in rejections:
        print(f"    rejected [{r.get('verdict')}] {r.get('quote', '?')!r}")

    results[key] = {
        "source": sample_name.strip(),
        "doc_type": doc_type,
        "ner_wall_clock_seconds": round(ner_wall, 2),
        "entity_count": len(entities),
        "condition_count": len(conditions),
        "conditions": [c.get("name") for c in conditions],
        "medication_count": len(medications),
        "medications": [m.get("drug") for m in medications],
        "observation_count": len(observations),
        "rules_only_flag_count": len(rules_flags),
        "hybrid_wall_clock_seconds": round(hybrid_wall, 2),
        "hybrid_accepted_count": len(hybrid_flags),
        "hybrid_accepted_flags": hybrid_flags,
        "hybrid_rejected_count": len(rejections),
        "hybrid_rejected_candidates": rejections,
    }

out_path = Path("data/mtsamples/remaining_8_results.json")
out_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
print(f"\n{'='*60}")
print(f"Done. Results saved to {out_path}")
print(f"{'='*60}")
