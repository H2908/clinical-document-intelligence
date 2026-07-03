"""Re-run hybrid mode on both MTSamples documents, this time capturing
EVERY rejected flag (not just accepted ones) with its verdict, so the
grounding-generalisation evidence is a committed, re-runnable artifact
rather than terminal scrollback.

Uses logging.Handler to intercept log.warning() calls from flag_agent
and parse out VERDICT lines, since the rejection detail is currently
only surfaced via logging, not returned by detect_flags().
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
    """Captures VERDICT log lines and the immediately preceding
    'LLM quote' / 'LLM description' lines emitted by the hybrid
    validator, reconstructing each rejection as a structured record."""

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
            # Extract the verdict label (first word/phrase after "VERDICT:")
            m = re.match(r"VERDICT:\s*([a-z-]+)", msg)
            self._pending["verdict"] = m.group(1) if m else "unknown"
            self.records.append(dict(self._pending))
            self._pending = {}


capture = VerdictCapture()
capture.setLevel(logging.WARNING)
_flag_logger = logging.getLogger("agents.flag_agent")
_flag_logger.addHandler(capture)
# Disable propagation to root while capturing, so each VERDICT line is
# captured exactly once. Fixed after discovering the original dual
# registration (module logger + root logger) caused every VERDICT to be
# captured twice - a real JSONL duplicate, not just a display artifact,
# confirmed by inspecting rejected_candidates array length directly.
_flag_logger.propagate = False

DOCS = {
    "pneumonia_copd_discharge": {
        "path": Path("data/mtsamples/pdfs/pneumonia_copd_discharge.pdf"),
        "doc_type": "discharge_summary",
        "source": "MTSamples - Pneumonia & COPD - Discharge Summary",
    },
    "afib_consult": {
        "path": Path("data/mtsamples/pdfs/afib_consult.pdf"),
        "doc_type": "clinic_letter",
        "source": "MTSamples - Atrial Fibrillation - Consult",
    },
}

results = {}

for key, meta in DOCS.items():
    print(f"\n{'='*60}")
    print(f"Processing: {key}  (mode=hybrid, full capture)")
    print(f"{'='*60}")

    capture.records = []  # reset per document

    result = process_document(
        file_path=meta["path"],
        document_id=f"mtsamples_{key}",
        patient_id="mtsamples_generalisation_check",
        document_date=date.today(),
        doc_type=meta["doc_type"],
    )
    entities = result.get("entities", [])
    for e in entities:
        e["document_id"] = f"mtsamples_{key}"

    documents_for_flags = [{
        "document_id": f"mtsamples_{key}",
        "document_date": date.today().isoformat(),
        "extracted_text": result["document"].get("extracted_text", ""),
    }]

    t0 = time.time()
    flags, flag_meta = detect_flags(
        patient_id="mtsamples_generalisation_check",
        entities=entities,
        documents=documents_for_flags,
        mode="hybrid",
    )
    wall = time.time() - t0

    rejections = list(capture.records)

    print(f"  Wall clock: {wall:.2f}s")
    print(f"  Accepted flags: {len(flags)}")
    print(f"  Rejected candidates: {len(rejections)}")
    verdict_counts = {}
    for r in rejections:
        v = r.get("verdict", "unknown")
        verdict_counts[v] = verdict_counts.get(v, 0) + 1
    for v, c in sorted(verdict_counts.items()):
        print(f"    {v}: {c}")

    results[key] = {
        "source": meta["source"],
        "mode": "hybrid",
        "wall_clock_seconds": round(wall, 2),
        "accepted_flag_count": len(flags),
        "accepted_flags": flags,
        "rejected_candidate_count": len(rejections),
        "rejected_candidates": rejections,
        "verdict_summary": verdict_counts,
    }

out_path = Path("data/mtsamples/hybrid_check_results_full.json")
out_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
print(f"\n{'='*60}")
print(f"Full results (including rejections) saved to {out_path}")
print(f"{'='*60}")
