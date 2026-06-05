"""
Contradiction agent — Phase 3 Task 4. Patient-safety critical.

Detects cross-document conflicts. Example:
    Doc A: "NKDA" (no known drug allergies)
    Doc B: "Penicillin allergy — rash"

Design: pure LLM (Claude), with strict prompt constraints:
  - Both source documents must be cited from the patient's actual docs
  - Conflicting statements must be quoted exactly from entity text
  - Agent must explain the contradiction, not just assert it
  - On uncertainty, return [] — false positives are worse than misses here

Output contract (per DB_SCHEMA.md CORE.contradiction):
    list[dict] with keys:
        severity         (HIGH | MEDIUM | LOW)
        category         (str — e.g. "ALLERGY", "MEDICATION_STATUS")
        doc_a_id         (str — first document)
        doc_a_statement  (str — quoted text from doc A)
        doc_b_id         (str — second document)
        doc_b_statement  (str — quoted text from doc B)
        explanation      (str — agent's reasoning)
"""

from __future__ import annotations
import os
import json
import logging
from collections import defaultdict
from datetime import date

from anthropic import Anthropic

log = logging.getLogger(__name__)

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


# ─── Public API ──────────────────────────────────────────────────────

def find_contradictions(
    patient_id: str,
    entities: list[dict],
    documents: list[dict],
) -> list[dict]:
    """
    Surface contradictions across documents. Returns [] if fewer than
    two documents or if no API key configured.
    """
    if len(documents) < 2:
        log.info("contradiction_agent: skipping — only %d document(s)", len(documents))
        return []

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.warning("contradiction_agent: ANTHROPIC_API_KEY not set; skipping")
        return []

    # Group entities by document
    by_doc: dict[str, list[dict]] = defaultdict(list)
    for e in entities:
        by_doc[e["document_id"]].append(e)

    # Build a per-document summary for the prompt
    doc_summaries = []
    for doc in documents:
        doc_id = doc["document_id"]
        doc_entities = by_doc.get(doc_id, [])
        if not doc_entities:
            continue
        # Pull the medically meaningful entities — drop the date entities and noise
        relevant = [
            {
                "type": e.get("entity_type"),
                "text": e.get("text"),
                "negated": e.get("negated"),
                "icd10": e.get("icd10_code"),
            }
            for e in doc_entities
            if e.get("entity_type") in ("Diagnosis", "Drug", "Conflict")
        ]
        if not relevant:
            continue
        doc_summaries.append({
            "document_id": doc_id,
            "doc_type": doc.get("doc_type"),
            "document_date": str(doc.get("document_date")) if doc.get("document_date") else None,
            "entities": relevant,
        })

    if len(doc_summaries) < 2:
        log.info("contradiction_agent: skipping — <2 docs with relevant entities")
        return []

    # Single LLM call across the whole patient corpus
    try:
        contradictions = _llm_find_contradictions(doc_summaries, documents)
    except Exception as e:
        log.exception("contradiction_agent: LLM call failed")
        return []

    log.info("contradiction_agent: found %d contradictions", len(contradictions))
    return contradictions


# ─── LLM call ────────────────────────────────────────────────────────

def _llm_find_contradictions(
    doc_summaries: list[dict],
    documents: list[dict],
) -> list[dict]:
    valid_doc_ids = {d["document_id"] for d in documents}

    prompt = _build_prompt(doc_summaries)
    client = _get_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()

    # Strip markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("contradiction_agent: LLM returned non-JSON; rejecting")
        return []

    if not isinstance(parsed, list):
        return []

    validated = []
    for c in parsed:
        if not isinstance(c, dict):
            continue
        # Required fields
        required = ("severity", "category", "doc_a_id", "doc_a_statement",
                    "doc_b_id", "doc_b_statement", "explanation")
        if not all(k in c for k in required):
            continue
        # Severity validation
        if c["severity"] not in ("HIGH", "MEDIUM", "LOW"):
            continue
        # Both doc IDs must be real
        if c["doc_a_id"] not in valid_doc_ids or c["doc_b_id"] not in valid_doc_ids:
            log.warning("contradiction_agent: rejecting — unknown doc id (%s or %s)",
                        c["doc_a_id"], c["doc_b_id"])
            continue
        # Doc A and Doc B must be different
        if c["doc_a_id"] == c["doc_b_id"]:
            log.warning("contradiction_agent: rejecting — same doc cited for both sides")
            continue
        validated.append(c)

    return validated


def _build_prompt(doc_summaries: list[dict]) -> str:
    return f"""You are a clinical safety reviewer helping an NHS doctor identify CONTRADICTIONS between a patient's documents before an appointment.

A contradiction is when two documents make DIRECTLY OPPOSING factual claims about the patient, such as:
- One document says "NKDA" / "no known allergies"; another lists a specific allergy
- One document says a medication is current; another says it was stopped
- One document records a diagnosis as present; another records it as ruled out
- Numerical conflicts (e.g. "eGFR 80" vs "eGFR 32" within close timeframe)

PATIENT DOCUMENTS:
{json.dumps(doc_summaries, indent=2, default=str)}

YOUR TASK:
Identify direct contradictions between pairs of documents.

STRICT RULES — read carefully:
1. Output ONLY a JSON array. No prose, no markdown fences.
2. Each contradiction MUST cite TWO different document_ids from the documents above.
3. doc_a_statement and doc_b_statement must be EXACT entity text from the documents shown. Do not paraphrase.
4. "category" is a short code: ALLERGY, MEDICATION_STATUS, DIAGNOSIS_STATUS, NUMERICAL, OTHER.
5. severity: HIGH (allergy/medication conflicts), MEDIUM (diagnosis status), LOW (minor inconsistencies).
6. The explanation MUST state why these are contradictory — be specific.
7. Do NOT report:
   - The same document conflicting with itself
   - Different facts that don't actually conflict (e.g. two different diagnoses can both be true)
   - Inferred contradictions where one side isn't explicitly stated
8. If no clear contradictions exist, return [].
9. Be conservative. False positives waste doctor time and erode trust.

Output format (JSON array only):
[
  {{
    "severity": "HIGH",
    "category": "ALLERGY",
    "doc_a_id": "doc_xxx",
    "doc_a_statement": "exact text from doc A",
    "doc_b_id": "doc_yyy",
    "doc_b_statement": "exact text from doc B",
    "explanation": "Why these contradict, in clinical terms."
  }}
]

OUTPUT:"""


# ─── CLI test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python -m agents.contradiction_agent <patient_id>")
        sys.exit(1)

    from database.snowflake_reader import (
        read_entities_for_patient,
        read_documents_for_patient,
    )
    patient_id = sys.argv[1]
    entities = read_entities_for_patient(patient_id)
    documents = read_documents_for_patient(patient_id)
    contras = find_contradictions(patient_id, entities, documents)
    print(json.dumps(contras, indent=2, default=str))