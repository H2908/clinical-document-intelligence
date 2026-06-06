"""
Flag agent — Phase 3 Task 3. Patient-safety critical.

Hybrid design:
  1. Deterministic rules catch known patterns (100% reliable).
  2. Claude generates human-readable descriptions for surfaced flags.
  3. Claude does a second pass on remaining entities to catch edge cases,
     tagged explicitly as "AI-detected" so the doctor knows the provenance.

Output contract (per DB_SCHEMA.md CORE.flag):
    list[dict] with keys:
        severity            (HIGH | MEDIUM | LOW)
        category            (str — short code, e.g. "ALLERGY_CONFLICT")
        description         (str — natural language for the doctor)
        source_document_id  (str — provenance)
"""

from __future__ import annotations
import os
import json
import logging
from datetime import date, timedelta
from collections import defaultdict
from agents.prompts import build_flag_second_pass, get_prompt_version

from anthropic import Anthropic

log = logging.getLogger(__name__)

# Claude client — initialised lazily so import-time failures don't kill the orchestrator
_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()  # picks up ANTHROPIC_API_KEY from env
    return _client


# ─── Known-dangerous patterns (extend over time) ────────────────────
# Map: documented allergy term -> drug-name fragments to flag if present
_ALLERGY_CONFLICTS = {
    "penicillin allergy": ["penicillin", "amoxicillin", "ampicillin", "co-amoxiclav",
                           "flucloxacillin", "piperacillin"],
    "penicillin": ["penicillin", "amoxicillin", "ampicillin", "co-amoxiclav",
                   "flucloxacillin", "piperacillin"],
    "nsaid allergy": ["ibuprofen", "naproxen", "diclofenac", "aspirin"],
    "aspirin allergy": ["aspirin", "ibuprofen", "naproxen"],
    "sulfa allergy": ["sulfamethoxazole", "co-trimoxazole", "trimethoprim"],
    "statin allergy": ["atorvastatin", "simvastatin", "rosuvastatin", "pravastatin"],
}

# Conditions where >90 days without follow-up is concerning
_CHRONIC_CONDITIONS_NEEDING_FOLLOWUP = {
    "diabetes", "heart failure", "ischaemic heart disease",
    "chronic kidney disease", "ckd", "copd", "atrial fibrillation",
    "hypertension", "dilated cardiomyopathy",
}

FOLLOWUP_DAYS_THRESHOLD = 90


# ─── Public API ──────────────────────────────────────────────────────

def detect_flags(
    patient_id: str,
    entities: list[dict],
    documents: list[dict],
) -> list[dict]:
    """
    Detect risk flags for one patient. Combines deterministic rules
    with an LLM second-pass for edge cases.
    """
    flags: list[dict] = []

    # Filter out negated entities — patient safety
    active = [e for e in entities if not e.get("negated")]

    # Run each deterministic rule
    flags.extend(_check_allergy_drug_conflicts(active))
    flags.extend(_check_duplicate_medications(active))
    flags.extend(_check_overdue_followups(active, documents))

    # LLM second-pass — only if we have data and an API key
    if active and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            llm_flags = _llm_second_pass(active, documents, existing_flags=flags)
            flags.extend(llm_flags)
        except Exception as e:
            log.exception("LLM second-pass failed; continuing with deterministic flags only")

    log.info("flag_agent: produced %d flags (%d active entities)",
             len(flags), len(active))
    return flags


# ─── Rule 1 — Allergy vs drug conflicts ──────────────────────────────

def _check_allergy_drug_conflicts(entities: list[dict]) -> list[dict]:
    """Detect when a patient has Drug X but also has Drug-X allergy documented."""
    flags = []

    # Find documented allergies (Conflict entities)
    allergies = []
    for e in entities:
        if e.get("entity_type") == "Conflict":
            text_lower = (e.get("text") or "").strip().lower()
            for known in _ALLERGY_CONFLICTS:
                if known in text_lower:
                    allergies.append((known, e))

    # Find drugs
    drugs = [e for e in entities if e.get("entity_type") == "Drug"]

    # Cross-reference
    seen_keys = set()
    for allergy_term, allergy_entity in allergies:
        dangerous_drugs = _ALLERGY_CONFLICTS[allergy_term]
        for drug in drugs:
            drug_text = (drug.get("text") or "").strip().lower()
            for danger in dangerous_drugs:
                if danger in drug_text:
                    key = (allergy_entity["document_id"], drug["document_id"], danger)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    flags.append({
                        "severity": "HIGH",
                        "category": "ALLERGY_CONFLICT",
                        "description": (
                            f"Patient has documented {allergy_term} but is on "
                            f"{drug['text'].strip()}. Verify before prescribing."
                        ),
                        "source_document_id": drug["document_id"],
                    })
    return flags


# ─── Rule 2 — Duplicate medications ──────────────────────────────────

def _check_duplicate_medications(entities: list[dict]) -> list[dict]:
    """Same drug appears in multiple documents — possible duplicate prescription."""
    flags = []
    drug_docs: dict[str, set[str]] = defaultdict(set)

    for e in entities:
        if e.get("entity_type") != "Drug":
            continue
        # Normalise: take the first word of the drug text as the drug name
        drug_text = (e.get("text") or "").strip().lower()
        drug_name = drug_text.split()[0] if drug_text else ""
        if not drug_name or len(drug_name) < 3:
            continue
        drug_docs[drug_name].add(e["document_id"])

    for drug_name, doc_ids in drug_docs.items():
        if len(doc_ids) >= 2:
            # Report once, point at the most recent document
            flags.append({
                "severity": "MEDIUM",
                "category": "POSSIBLE_DUPLICATE_MEDICATION",
                "description": (
                    f"{drug_name.capitalize()} mentioned across "
                    f"{len(doc_ids)} documents. Confirm current dose."
                ),
                "source_document_id": sorted(doc_ids)[-1],
            })
    return flags


# ─── Rule 3 — Overdue follow-ups for chronic conditions ──────────────

def _check_overdue_followups(
    entities: list[dict],
    documents: list[dict],
) -> list[dict]:
    """Chronic condition documented but no document for >90 days."""
    flags = []
    today = date.today()
    threshold = today - timedelta(days=FOLLOWUP_DAYS_THRESHOLD)

    # Find chronic conditions and the most recent doc they appear in
    condition_latest: dict[str, tuple[date, str]] = {}
    for e in entities:
        if e.get("entity_type") != "Diagnosis":
            continue
        text_lower = (e.get("text") or "").strip().lower()
        matched = next(
            (c for c in _CHRONIC_CONDITIONS_NEEDING_FOLLOWUP if c in text_lower),
            None,
        )
        if not matched:
            continue
        doc_date = e.get("document_date")
        if not isinstance(doc_date, date):
            continue
        if matched not in condition_latest or doc_date > condition_latest[matched][0]:
            condition_latest[matched] = (doc_date, e["document_id"])

    for condition, (latest_date, doc_id) in condition_latest.items():
        if latest_date < threshold:
            days_since = (today - latest_date).days
            flags.append({
                "severity": "MEDIUM",
                "category": "OVERDUE_FOLLOWUP",
                "description": (
                    f"{condition.title()} last documented {days_since} days ago "
                    f"({latest_date.isoformat()}). Consider review."
                ),
                "source_document_id": doc_id,
            })
    return flags


# ─── LLM second-pass ─────────────────────────────────────────────────

def _llm_second_pass(
    entities: list[dict],
    documents: list[dict],
    existing_flags: list[dict],
) -> list[dict]:
    """
    Ask Claude to identify additional flags the rules missed.
    Strict prompt: must return JSON, must cite source_document_id from the
    provided list, must not invent drug interactions not in the entities.
    """
    # Build a compact summary for the prompt
    entity_summary = [
        {
            "type": e.get("entity_type"),
            "text": e.get("text"),
            "doc": e.get("document_id"),
            "date": str(e.get("document_date")) if e.get("document_date") else None,
            "icd10": e.get("icd10_code"),
        }
        for e in entities
    ]
    valid_doc_ids = {d["document_id"] for d in documents}

    prompt = build_flag_second_pass(entity_summary, existing_flags)
    log.info("flag_agent: using prompt version %s", get_prompt_version("flag_second_pass"))

    client = _get_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("LLM returned non-JSON; ignoring second-pass output")
        return []

    if not isinstance(parsed, list):
        return []

    # Validate every flag the LLM produced
    validated = []
    for f in parsed:
        if not isinstance(f, dict):
            continue
        if not all(k in f for k in ("severity", "category", "description", "source_document_id")):
            continue
        if f["severity"] not in ("HIGH", "MEDIUM", "LOW"):
            continue
        # Source document MUST be from the patient's actual docs
        if f["source_document_id"] not in valid_doc_ids:
            log.warning("LLM cited unknown doc %s; rejecting flag", f["source_document_id"])
            continue
        # Tag as AI-detected so the doctor knows
        if not f["category"].startswith("AI_"):
            f["category"] = f"AI_{f['category']}"
        validated.append(f)

    log.info("LLM second-pass produced %d validated flags", len(validated))
    return validated


def _build_flag_prompt(entity_summary: list[dict], existing_flags: list[dict]) -> str:
    return f"""You are a clinical safety reviewer assisting an NHS doctor reviewing a patient's chart before an appointment. You DO NOT provide medical advice — you only surface patterns the doctor should verify.

PATIENT ENTITIES (extracted from documents):
{json.dumps(entity_summary, indent=2, default=str)}

FLAGS ALREADY DETECTED BY RULES (do not duplicate these):
{json.dumps([{"category": f["category"], "description": f["description"]} for f in existing_flags], indent=2)}

YOUR TASK:
Identify any additional clinically relevant patterns the doctor should verify. Examples:
- Inconsistent medication regimens across documents
- Patterns suggesting medication non-adherence
- Conditions documented without corresponding treatment
- Investigations ordered but no result documented

STRICT RULES:
1. Output ONLY a JSON array of flag objects. No prose, no markdown fences.
2. Each flag: {{"severity": "HIGH"|"MEDIUM"|"LOW", "category": "SHORT_CODE", "description": "natural language for doctor", "source_document_id": "doc_..."}}
3. source_document_id MUST be one that appears in the entities above. Never invent.
4. Do not invent drug names, interactions, or conditions not present in the entities.
5. If nothing additional to flag, return [].
6. Maximum 5 flags. Be conservative — false positives waste doctor time.
7. Use clinical language but keep descriptions under 30 words.

OUTPUT (JSON array only):"""


# ─── CLI test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python -m agents.flag_agent <patient_id>")
        sys.exit(1)

    from database.snowflake_reader import (
        read_entities_for_patient,
        read_documents_for_patient,
    )
    patient_id = sys.argv[1]
    entities = read_entities_for_patient(patient_id)
    documents = read_documents_for_patient(patient_id)
    flags = detect_flags(patient_id, entities, documents)
    print(json.dumps(flags, indent=2, default=str))