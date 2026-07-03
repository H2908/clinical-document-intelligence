"""Re-run afib_consult 3 more times (hybrid mode, fixed logging) to
determine whether the earlier 0-accepted/0-rejected result was genuine
LLM sampling variance (consistent with the 3/1/0/2/0 pattern seen in
the 5-rep ablation run) or a new, unexplained regression.

Uses the corrected VerdictCapture (module logger only, propagation
disabled) so counts are trustworthy without manual dedup.
"""
import json
import logging
import re
import time
from datetime import date
from pathlib import Path

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

DOC_PATH = Path("data/mtsamples/pdfs/afib_consult.pdf")

result = process_document(
    file_path=DOC_PATH,
    document_id="mtsamples_afib_consult",
    patient_id="mtsamples_generalisation_check",
    document_date=date.today(),
    doc_type="clinic_letter",
)
entities = result.get("entities", [])
for e in entities:
    e["document_id"] = "mtsamples_afib_consult"
documents_for_flags = [{
    "document_id": "mtsamples_afib_consult",
    "document_date": date.today().isoformat(),
    "extracted_text": result["document"].get("extracted_text", ""),
}]

runs = []
for rep in range(3):
    print(f"\n{'='*60}")
    print(f"afib_consult rep {rep} (post-logging-fix, post-Guard3-fix)")
    print(f"{'='*60}")
    capture.records = []
    t0 = time.time()
    flags, metadata = detect_flags(
        "mtsamples_generalisation_check", entities, documents_for_flags
    )
    wall = time.time() - t0
    rejections = list(capture.records)

    for f in flags:
        for k, v in f.items():
            if hasattr(v, "isoformat"):
                f[k] = v.isoformat()

    print(f"  Wall clock: {wall:.2f}s")
    print(f"  Accepted: {len(flags)}")
    print(f"  Rejected: {len(rejections)}")
    for r in rejections:
        print(f"    [{r.get('verdict')}] {r.get('quote', '?')!r}")
    for f in flags:
        print(f"    ACCEPTED [{f.get('severity')}] {f.get('clinical_subject')}: {f.get('source_quote')!r}")

    runs.append({
        "rep": rep,
        "wall_clock_seconds": round(wall, 2),
        "accepted_count": len(flags),
        "accepted_flags": flags,
        "rejected_count": len(rejections),
        "rejected_candidates": rejections,
    })

out_path = Path("data/mtsamples/afib_consult_repeat_check.json")
out_path.write_text(json.dumps(runs, indent=2, default=str), encoding="utf-8")
print(f"\n{'='*60}")
print(f"Saved to {out_path}")
counts = [r["accepted_count"] for r in runs]
print(f"Accepted-flag counts across 3 reps: {counts}")
print(f"{'='*60}")
