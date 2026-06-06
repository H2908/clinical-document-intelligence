"""
Briefing agent — Phase 3 Task 5.

Synthesises everything (entities, timeline, flags, contradictions) into
one structured briefing for the doctor's pre-appointment screen.

Design:
  - Deterministic extraction of structured fields (conditions, meds, results)
  - LLM-generated narrative summary — STRICTLY factual, no clinical advice

Output contract (matches GET /briefing response body + MART.patient_summary):
    {
        "patient_id":          str,
        "summary":             str,         # 2-3 sentence factual overview
        "active_conditions":   list[dict],  # {name, icd10_code, source_document_id}
        "current_medications": list[dict],  # {drug, source_document_id}
        "recent_results":      list[dict],  # {test, value, date}  -- empty until lab parser
        "open_flags":          list[dict],  # subset from flag_agent
        "contradictions":      list[dict],  # subset from contradiction_agent
        "generated_at":        str (ISO timestamp)
    }
"""

from __future__ import annotations
import os
import json
import logging
from datetime import datetime
from collections import OrderedDict

from anthropic import Anthropic

log = logging.getLogger(__name__)

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


# Reuse the same noise terms from timeline_agent — these are NER false positives
_NOISE_TERMS = {
    "icd-10", "icd10", "lvef", "measured", "consistent with",
    "patient reports", "tolerated", "nurse", "bloods", "egfr",
    "nyha class ii", "cardiac medications", "heart failure therapy",
    "medication titration", "echocardiogram", "exposure", "rash",
    "β-lactams", "mill lane", "bristol", "on", "aspirin 75 mg",
}


def _is_noise(text: str) -> bool:
    if not text:
        return True
    t = text.strip().lower()
    if t in _NOISE_TERMS:
        return True
    if "\n" in t:  # multi-line means it captured a header
        return True
    if len(t) <= 3:
        return True
    return False


# ─── Public API ──────────────────────────────────────────────────────

def build_briefing(
    patient_id: str,
    entities: list[dict],
    documents: list[dict],
    timeline_events: list[dict],
    flags: list[dict],
    contradictions: list[dict],
) -> dict:
    """
    Build the pre-appointment briefing for one patient.
    """
    active_conditions   = _extract_conditions(entities)
    current_medications = _extract_medications(entities)
    recent_results      = []  # populated by lab parser in Phase 4

    # Open flags = flags from flag_agent that aren't resolved
    open_flags = [f for f in flags if f.get("status", "open") == "open"]

    # Open contradictions
    open_contras = [c for c in contradictions if c.get("status", "open") == "open"]

    # LLM-generated narrative summary
    summary = ""
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            summary = _generate_summary(
                patient_id=patient_id,
                conditions=active_conditions,
                medications=current_medications,
                open_flags=open_flags,
                contradictions=open_contras,
                documents=documents,
            )
        except Exception as e:
            log.exception("briefing_agent: summary generation failed")
            summary = ""

    briefing = {
        "patient_id":          patient_id,
        "summary":             summary,
        "active_conditions":   active_conditions,
        "current_medications": current_medications,
        "recent_results":      recent_results,
        "open_flags":          open_flags,
        "contradictions":      open_contras,
        "generated_at":        datetime.utcnow().isoformat() + "Z",
    }

    log.info("briefing_agent: %d conditions, %d meds, %d flags, %d contradictions",
             len(active_conditions), len(current_medications),
             len(open_flags), len(open_contras))
    return briefing


# ─── Deterministic extraction ────────────────────────────────────────

def _extract_conditions(entities: list[dict]) -> list[dict]:
    """
    Active conditions = non-negated Diagnosis entities, deduplicated by text.
    Keeps the earliest source document for provenance.
    """
    seen: OrderedDict[str, dict] = OrderedDict()
    for e in entities:
        if e.get("entity_type") != "Diagnosis":
            continue
        if e.get("negated"):
            continue
        text = (e.get("text") or "").strip()
        if _is_noise(text):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen[key] = {
            "name": text,
            "icd10_code": e.get("icd10_code"),
            "source_document_id": e["document_id"],
        }
    return list(seen.values())


def _extract_medications(entities: list[dict]) -> list[dict]:
    """
    Current medications = non-negated Drug entities, deduplicated by drug-name root.
    """
    seen: OrderedDict[str, dict] = OrderedDict()
    for e in entities:
        if e.get("entity_type") != "Drug":
            continue
        if e.get("negated"):
            continue
        text = (e.get("text") or "").strip()
        if not text or len(text) < 3:
            continue
        # Dedupe on first word (drug name root)
        key = text.split()[0].lower() if text.split() else ""
        if not key or key in seen:
            continue
        seen[key] = {
            "drug": text,
            "normalised": e.get("normalised_value"),
            "source_document_id": e["document_id"],
        }
    return list(seen.values())


# ─── LLM narrative ───────────────────────────────────────────────────

def _generate_summary(
    patient_id: str,
    conditions: list[dict],
    medications: list[dict],
    open_flags: list[dict],
    contradictions: list[dict],
    documents: list[dict],
) -> str:
    """Generate a 2-3 sentence factual summary. STRICTLY no clinical advice."""

    facts = {
        "active_conditions":   [c["name"] for c in conditions],
        "current_medications": [m["drug"] for m in medications],
        "document_count":      len(documents),
        "high_severity_flag_count": sum(1 for f in open_flags if f.get("severity") == "HIGH"),
        "open_flag_count":     len(open_flags),
        "contradiction_count": len(contradictions),
    }

    prompt = f"""You are writing the opening line of an ADMINISTRATIVE pre-appointment briefing for an NHS doctor. This is NOT clinical advice — it is a factual summary of what the patient's chart contains.

PATIENT FACTS (extracted from documents):
{json.dumps(facts, indent=2)}

WRITE: 2-3 short sentences (max 60 words total) summarising what is in the chart.

STRICT RULES:
1. Plain factual statements only. No clinical opinions. No "well-managed", no "stable", no "appropriate".
2. Reference only what is in the facts above. Do not invent.
3. Use neutral verbs: "documented", "recorded", "noted", "listed".
4. If contradictions or HIGH-severity flags exist, mention the count — do not interpret.
5. No advice, no recommendations, no judgement.
6. Output ONLY the summary text. No quotes, no preamble, no markdown.

EXAMPLE OF GOOD OUTPUT:
"Chart contains 3 documented conditions, 2 current medications recorded across 4 documents. 1 HIGH-severity flag and 0 contradictions noted for review."

EXAMPLE OF BAD OUTPUT (do not write this):
"Patient appears stable with well-managed cardiovascular disease on appropriate therapy."

OUTPUT:"""

    client = _get_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    summary = response.content[0].text.strip()

    # Strip any quotes the model might have wrapped around its output
    if summary.startswith('"') and summary.endswith('"'):
        summary = summary[1:-1]
    if summary.startswith("'") and summary.endswith("'"):
        summary = summary[1:-1]

    return summary


# ─── CLI test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python -m agents.briefing_agent <patient_id>")
        sys.exit(1)

    from database.snowflake_reader import (
        read_entities_for_patient,
        read_documents_for_patient,
    )
    from agents.timeline_agent import build_timeline
    from agents.flag_agent import detect_flags
    from agents.contradiction_agent import find_contradictions

    patient_id = sys.argv[1]
    entities = read_entities_for_patient(patient_id)
    documents = read_documents_for_patient(patient_id)

    timeline_events = build_timeline(entities, documents)
    flags = detect_flags(patient_id, entities, documents)
    contradictions = find_contradictions(patient_id, entities, documents)

    briefing = build_briefing(
        patient_id=patient_id,
        entities=entities,
        documents=documents,
        timeline_events=timeline_events,
        flags=flags,
        contradictions=contradictions,
    )
    print(json.dumps(briefing, indent=2, default=str))