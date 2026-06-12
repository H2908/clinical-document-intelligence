"""
Paper Day 3 — held-out evaluation runner.

Usage:
    python -m evaluation.runner --patients pat_test_01 \
        --conditions all --reps 5 \
        --out evaluation/results/smoke.jsonl

Conditions:
    rules_only          — deterministic; forced to 1 rep
    llm_naive           — LLM-only baseline, raw doc text, no provenance discipline
    llm_thoughtful      — LLM-only baseline, carefully prompted
    hybrid_validated    — rules + LLM second-pass + Guard 3 (v1.3) ON
    hybrid_unvalidated  — rules + LLM second-pass + Guard 3 (v1.3) OFF (ablation)

Each (patient, condition, sampling_run) tuple produces one JSONL row.

The runner attaches a per-call MemoryHandler to the agents.flag_agent logger,
captures all log records during the call, then regex-extracts validator
verdicts into a structured rejection_trace. The validator code (v1.3, frozen)
is NOT modified — this is pure telemetry.

Row schema (locked at first run; do not change after held-out begins):
    run_id, experiment_id, timestamp_utc, patient_id, condition,
    sampling_run, model, temperature, instrument_version,
    input.document_ids,
    parsed_count, accepted_count, rejected_count,
    accepted_flags (full dicts with grounding_status),
    rejection_trace (list of {verdict, doc_id, quote, description, overlap, longest_run, best_other_doc, best_other_overlap}),
    wall_clock_seconds, errors
"""
import argparse
import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Ensure we can import from project root when run as a module
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

from agents.flag_agent import detect_flags  # noqa: E402
from database.snowflake_reader import (  # noqa: E402
    read_entities_for_patient,
    read_documents_for_patient,
)

log = logging.getLogger("evaluation.runner")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# Lock schema constants here.
EXPERIMENT_ID = "paper-instrument-v1-3-heldout-smoke"
INSTRUMENT_VERSION = "v1.3"
MODEL_STRING = "claude-sonnet-4-6"
TEMPERATURE = 0.7

from evaluation.conditions import (
    ALL_CONDITIONS as CONDITIONS,
    DETERMINISTIC_CONDITIONS,
    apply_condition_env,
    clear_condition_env,
    is_deterministic,
)

# ---------------------------------------------------------------------------
# Log capture
# ---------------------------------------------------------------------------
class CaptureHandler(logging.Handler):
    """In-memory log handler. Collects all records for a single call."""

    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        # Pre-format the message so we can read it later without losing args
        try:
            record.message = record.getMessage()
        except Exception:
            record.message = str(record.msg)
        self.records.append(record)


VERDICT_RE = re.compile(r"VERDICT:\s+([\w\-]+)")
DOC_RE = re.compile(r"REJECTION on doc (\S+)")
QUOTE_RE = re.compile(r"LLM quote: (.+)")
DESCRIPTION_RE = re.compile(r"LLM description: (.+)")
OVERLAP_RE = re.compile(r"overlap[^=]*=(\d+\.\d+)")
RUN_RE = re.compile(r"longest contiguous run=(\d+)")
OTHER_DOC_RE = re.compile(r"with (\S+)=(\d+\.\d+)")


def extract_rejection_trace(records: list[logging.LogRecord]) -> list[dict]:
    """Parse captured log records into structured rejection events.

    Each rejection is a block beginning with 'HYBRID VALIDATOR REJECTION on doc'
    and ending with a VERDICT line. We walk the records in order, accumulating
    context, and snapshot when we see a VERDICT.
    """
    trace: list[dict] = []
    current: dict | None = None

    for r in records:
        msg = getattr(r, "message", str(r.msg))

        if "HYBRID VALIDATOR REJECTION on doc" in msg:
            current = {"event": "rejection"}
            m = DOC_RE.search(msg)
            if m:
                current["doc_id"] = m.group(1)
            continue

        if current is None:
            continue

        if "LLM quote:" in msg:
            m = QUOTE_RE.search(msg)
            if m:
                current["quote"] = m.group(1).strip()
        elif "LLM description:" in msg:
            m = DESCRIPTION_RE.search(msg)
            if m:
                current["description"] = m.group(1).strip()
        elif "VERDICT:" in msg:
            m = VERDICT_RE.search(msg)
            if m:
                current["verdict"] = m.group(1)
            # Verdict line carries optional metrics; extract what's there.
            om = OVERLAP_RE.search(msg)
            if om:
                current["overlap"] = float(om.group(1))
            rm = RUN_RE.search(msg)
            if rm:
                current["longest_run"] = int(rm.group(1))
            otm = OTHER_DOC_RE.search(msg)
            if otm:
                current["best_other_doc"] = otm.group(1)
                try:
                    current["best_other_overlap"] = float(otm.group(2))
                except ValueError:
                    pass
            trace.append(current)
            current = None

    return trace


# --------------------------------------------------------------------------
# Condition execution
# ---------------------------------------------------------------------------

def run_single(
    patient_id: str,
    entities: list[dict],
    documents: list[dict],
    condition: str,
    sampling_run: int,
) -> dict:
    """Execute one (patient, condition, sampling_run) call.

    Returns a JSONL-ready dict.
    """
    run_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).isoformat()
    env = apply_condition_env(condition)

    flag_logger = logging.getLogger("agents.flag_agent")
    capture = CaptureHandler()
    capture.setLevel(logging.DEBUG)
    flag_logger.addHandler(capture)

    flags: list[dict] = []
    metadata: dict = {}
    err_str: str | None = None
    t0 = time.time()
    try:
        flags, metadata = detect_flags(patient_id, entities, documents)
    except Exception as e:
        log.exception("detect_flags failed for %s / %s", patient_id, condition)
        err_str = f"{type(e).__name__}: {e}"
    wall = time.time() - t0

    flag_logger.removeHandler(capture)
    clear_condition_env()

    rejection_trace = extract_rejection_trace(capture.records)

    # Split flags by origin where possible. The hybrid path returns rule_flags
    # first then llm_flags; the others are mode-pure.
    accepted_flags = []
    for f in flags:
        if isinstance(f, dict):
            accepted_flags.append(f)

    # Count parsed = accepted + rejected (visible from log trace).
    accepted_count = len(accepted_flags)
    rejected_count = len(rejection_trace)
    parsed_count = accepted_count + rejected_count

    row = {
        "run_id": run_id,
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": ts,
        "patient_id": patient_id,
        "condition": condition,
        "sampling_run": sampling_run,
        "model": MODEL_STRING,
        "temperature": TEMPERATURE,
        "instrument_version": INSTRUMENT_VERSION,
        "env_applied": env,
        "input": {
            "document_ids": [d["document_id"] for d in documents if "document_id" in d],
            "entity_count": len(entities),
        },
        "parsed_count": parsed_count,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "accepted_flags": accepted_flags,
        "rejection_trace": rejection_trace,
        "metadata": metadata,
        "wall_clock_seconds": round(wall, 3),
        "errors": [err_str] if err_str else [],
    }
    return row


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patients", required=True,
                    help="Comma-separated patient IDs, or 'pat_test_01'")
    ap.add_argument("--conditions", default="all",
                    help=f"Comma-separated or 'all'. Options: {','.join(CONDITIONS)}")
    ap.add_argument("--reps", type=int, default=5,
                    help="Sampling repetitions per (patient, condition); rules_only forced to 1")
    ap.add_argument("--out", required=True, help="Output JSONL path")
    args = ap.parse_args()

    patient_ids = [p.strip() for p in args.patients.split(",") if p.strip()]
    if args.conditions == "all":
        conditions = list(CONDITIONS)
    else:
        conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
        for c in conditions:
            if c not in CONDITIONS:
                raise SystemExit(f"Unknown condition: {c}. Must be one of {CONDITIONS}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("Experiment: %s", EXPERIMENT_ID)
    log.info("Patients:   %s", patient_ids)
    log.info("Conditions: %s", conditions)
    log.info("Reps:       %d (rules_only forced to 1)", args.reps)
    log.info("Output:     %s", out_path)
    log.info("=" * 60)

    total_rows = 0
    summary = {c: {"accepted": 0, "rejected": 0, "wall": 0.0, "n": 0} for c in conditions}

    with out_path.open("w", encoding="utf-8") as out_f:
        for patient_id in patient_ids:
            log.info("Loading entities/documents for %s ...", patient_id)
            try:
                entities = read_entities_for_patient(patient_id)
                documents = read_documents_for_patient(patient_id)
            except Exception as e:
                log.exception("Snowflake read failed for %s", patient_id)
                row = {
                    "run_id": str(uuid.uuid4()),
                    "experiment_id": EXPERIMENT_ID,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "patient_id": patient_id,
                    "errors": [f"snowflake_read: {type(e).__name__}: {e}"],
                }
                out_f.write(json.dumps(row, default=str) + "\n")
                continue

            log.info("  %d entities, %d documents", len(entities), len(documents))

            for condition in conditions:
                reps = 1 if is_deterministic(condition) else args.reps
                for sampling_run in range(reps):
                    log.info("  -> %s rep=%d/%d", condition, sampling_run + 1, reps)
                    row = run_single(
                        patient_id, entities, documents, condition, sampling_run,
                    )
                    out_f.write(json.dumps(row, default=str) + "\n")
                    out_f.flush()
                    total_rows += 1
                    summary[condition]["accepted"] += row["accepted_count"]
                    summary[condition]["rejected"] += row["rejected_count"]
                    summary[condition]["wall"] += row["wall_clock_seconds"]
                    summary[condition]["n"] += 1

    log.info("=" * 60)
    log.info("Done. %d rows written to %s", total_rows, out_path)
    log.info("=" * 60)
    log.info("%-22s %6s %10s %10s %10s",
             "condition", "n", "accepted", "rejected", "mean_wall_s")
    for c in conditions:
        s = summary[c]
        if s["n"]:
            mean_wall = s["wall"] / s["n"]
            log.info(
                "%-22s %6d %10d %10d %10.2f",
                c, s["n"], s["accepted"], s["rejected"], mean_wall,
            )
    log.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())