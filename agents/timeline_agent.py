"""
Timeline agent — Phase 3 Task 2.

Deterministic: walks entities + documents, produces chronological events.

Input contract:
    entities: list[dict] from snowflake_reader.read_entities_for_patient
    documents: list[dict] from snowflake_reader.read_documents_for_patient

Output contract (per NLP_OUTPUT.md / DB_SCHEMA.md CORE.timeline_event):
    list[dict] with keys:
        event_date         (str, ISO YYYY-MM-DD)
        event_type         (str: Diagnosis | Medication | Conflict | Document)
        title              (str: what to display)
        icd10_code         (str | None)
        source_document_id (str)
"""

from __future__ import annotations
import logging
from collections import defaultdict
from datetime import date

log = logging.getLogger(__name__)


def build_timeline(entities: list[dict], documents: list[dict]) -> list[dict]:
    """Build a chronological event list for one patient."""
    events: list[dict] = []

    # Quick lookup: document_id -> document_date (for entities without their own date)
    doc_dates: dict[str, date | None] = {}
    for doc in documents:
        doc_dates[doc["document_id"]] = doc.get("document_date")

    # Group entities by document for context
    by_doc: dict[str, list[dict]] = defaultdict(list)
    for e in entities:
        by_doc[e["document_id"]].append(e)

    # ─── 1. One "Document" event per document ──────────────────────
    # Gives the doctor a clean per-document anchor in the timeline.
    for doc in documents:
        if doc.get("document_date"):
            events.append({
                "event_date": _iso(doc["document_date"]),
                "event_type": "Document",
                "title": f"{_doc_type_label(doc.get('doc_type'))} — {doc.get('source') or 'unknown source'}",
                "icd10_code": None,
                "source_document_id": doc["document_id"],
            })

    # ─── 2. Medical entities, dated to their document ──────────────
    # Diagnoses, Drugs, and Conflicts get one event each.
    # Date = the document's date (not the Date entity inside the doc —
    # those are typically referral/follow-up dates, not when the
    # diagnosis was made).
    for doc_id, doc_entities in by_doc.items():
        doc_date = doc_dates.get(doc_id)
        if not doc_date:
            continue

        for e in doc_entities:
            # PATIENT SAFETY — never include negated entities in timeline
            if e.get("negated"):
                continue

            etype = e.get("entity_type")

            if etype == "Diagnosis":
                # Skip false-positive noise. _classify_span in medical_ner is
                # too permissive; filter obvious non-conditions here.
                if _is_likely_noise(e["text"]):
                    continue
                events.append({
                    "event_date": _iso(doc_date),
                    "event_type": "Diagnosis",
                    "title": e["text"],
                    "icd10_code": e.get("icd10_code"),
                    "source_document_id": doc_id,
                })

            elif etype == "Drug":
                events.append({
                    "event_date": _iso(doc_date),
                    "event_type": "Medication",
                    "title": e["text"],
                    "icd10_code": None,
                    "source_document_id": doc_id,
                })

            elif etype == "Conflict":
                # Allergies and similar — these are clinically critical
                events.append({
                    "event_date": _iso(doc_date),
                    "event_type": "Conflict",
                    "title": e["text"],
                    "icd10_code": None,
                    "source_document_id": doc_id,
                })

    # ─── 3. Sort newest first, deduplicate ─────────────────────────
    events = _dedupe(events)
    events.sort(key=lambda x: x["event_date"], reverse=True)

    log.info("timeline_agent: built %d events from %d entities, %d documents",
             len(events), len(entities), len(documents))
    return events


# ─── helpers ──────────────────────────────────────────────────────

# Common non-diagnosis tokens that the NER pass picks up as Diagnosis
# (place names, generic clinical context words). Lowercase comparison.
_NOISE_TERMS = {
    "icd-10", "icd10", "lvef", "measured", "consistent with",
    "patient reports", "tolerated", "nurse", "bloods", "egfr",
    "nyha class ii", "cardiac medications", "heart failure therapy",
    "medication titration", "echocardiogram", "exposure", "rash",
    "β-lactams", "mill lane", "bristol",
}


def _is_likely_noise(text: str) -> bool:
    """Filter clear false-positives from the Diagnosis stream."""
    if not text:
        return True
    t = text.strip().lower()
    if t in _NOISE_TERMS:
        return True
    # Pure ICD code (e.g. "I25.9") shouldn't be a Diagnosis on its own
    if len(t) <= 6 and any(c.isdigit() for c in t) and "." in t:
        return True
    # Single short word that's likely a fragment
    if len(t) <= 3:
        return True
    return False


def _doc_type_label(doc_type: str | None) -> str:
    """Human-readable label for the timeline."""
    if not doc_type:
        return "Document"
    return {
        "referral": "Referral",
        "clinic_letter": "Clinic Letter",
        "gp_note": "GP Note",
        "clinician_note": "Clinician Note",
        "lab_report": "Lab Report",
        "imaging": "Imaging",
    }.get(doc_type, doc_type.replace("_", " ").title())


def _iso(d) -> str:
    """Coerce any date-like value to ISO YYYY-MM-DD string."""
    if isinstance(d, date):
        return d.isoformat()
    return str(d)


def _dedupe(events: list[dict]) -> list[dict]:
    """Remove duplicate (date, type, title) tuples within the same document."""
    seen = set()
    out = []
    for e in events:
        key = (e["event_date"], e["event_type"], e["title"].lower(), e["source_document_id"])
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


# ─── CLI test ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import json
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python -m agents.timeline_agent <patient_id>")
        sys.exit(1)

    from database.snowflake_reader import (
        read_entities_for_patient,
        read_documents_for_patient,
    )
    patient_id = sys.argv[1]
    entities = read_entities_for_patient(patient_id)
    documents = read_documents_for_patient(patient_id)
    events = build_timeline(entities, documents)
    print(json.dumps(events, indent=2, default=str))

       