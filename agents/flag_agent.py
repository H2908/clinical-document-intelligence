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

from typing import Literal
from anthropic import Anthropic

FlagMode = Literal["rules_only", "llm_naive", "llm_thoughtful", "hybrid"]
DEFAULT_FLAG_MODE: FlagMode = "hybrid"
VALID_FLAG_MODES = ("rules_only", "llm_naive", "llm_thoughtful", "hybrid")


def detect_flags(
    patient_id: str,
    entities: list[dict],
    documents: list[dict],
    mode: FlagMode | None = None,
    llm_client: Anthropic | None = None,
) -> tuple[list[dict], dict]:
    """
    Detect risk flags. Four modes:

        rules_only       — deterministic rules only, zero LLM calls
        llm_naive        — naive LLM-only baseline on raw document text
        llm_thoughtful   — carefully prompted LLM-only baseline on raw doc text
        hybrid           — rules + constrained LLM second-pass (PRODUCTION)

    Returns (flags, metadata).

    Mode resolution order:
        explicit arg → FLAG_AGENT_MODE env var → DEFAULT_FLAG_MODE ('hybrid')
    """
    if mode is None:
        mode = os.environ.get("FLAG_AGENT_MODE", DEFAULT_FLAG_MODE)
    if mode not in VALID_FLAG_MODES:
        raise ValueError(
            f"Invalid FLAG_AGENT_MODE: {mode!r}. "
            f"Must be one of {VALID_FLAG_MODES}"
        )

    # Patient-safety: negated entities filtered for rules pipeline.
    # CRITICAL: llm_naive and llm_thoughtful do NOT use `active` —
    # they receive raw document text, not the entity list, to ensure
    # they're genuinely independent of the upstream NLP pipeline.
    active = [e for e in entities if not e.get("negated")]

    rule_flags: list[dict] = []
    llm_flags: list[dict] = []

    # Rules branch — runs for rules_only and hybrid only
    if mode in ("rules_only", "hybrid"):
        rule_flags.extend(_check_allergy_drug_conflicts(active))
        rule_flags.extend(_check_duplicate_medications(active))
        rule_flags.extend(_check_overdue_followups(active, documents))

    # LLM branches — never seen entity list except in hybrid mode
    if mode == "hybrid" and active:
        try:
            llm_flags = _llm_second_pass(
                active, documents,
                existing_flags=rule_flags,
                client=llm_client,
            )
        except Exception as e:
            log.exception("LLM second-pass failed in mode=hybrid")
            llm_flags = []

    elif mode == "llm_naive":
        try:
            llm_flags = _llm_only_naive_pass(documents, client=llm_client)
        except Exception as e:
            log.exception("LLM naive pass failed")
            llm_flags = []

    elif mode == "llm_thoughtful":
        try:
            llm_flags = _llm_only_thoughtful_pass(documents, client=llm_client)
        except Exception as e:
            log.exception("LLM thoughtful pass failed")
            llm_flags = []

    flags = rule_flags + llm_flags
    metadata = {
        "mode": mode,
        "n_rule_flags": len(rule_flags),
        "n_llm_flags": len(llm_flags),
        "n_active_entities": len(active),
        "n_total_entities": len(entities),
        "n_documents": len(documents),
        "prompt_version": (
            get_prompt_version("flag_second_pass")
            if mode in ("hybrid", "llm_naive", "llm_thoughtful")
            else None
        ),
    }

    log.info(
        "flag_agent: mode=%s rule_flags=%d llm_flags=%d total=%d",
        mode, len(rule_flags), len(llm_flags), len(flags),
    )

    return flags, metadata


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
    client: Anthropic | None = None,
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
    log.info(
        "flag_agent: using prompt version %s",
        get_prompt_version("flag_second_pass"),
    )

    # Build client fresh if not injected (no module-level cache)
    if client is None:
        client = Anthropic()

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        temperature=0.7,
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

def _llm_only_naive_pass(
    documents: list[dict],
    client: Anthropic | None = None,
) -> list[dict]:
    """
    Naive LLM-only baseline. Receives raw cleaned document text only.
    NO entity extraction. NO negation filtering. NO rule context.
    NO provenance enforcement.

    This is what unguarded prompting produces — the strawman baseline.

    REQUIRES: documents must include 'extracted_text' field.
              Gated on the reader SELECT fix + worker text-population fix.
    """
    if client is None:
        client = Anthropic()

    # Build raw corpus, tagged by document_id for citation tracking
    blocks = []
    for d in documents:
        text = d.get("extracted_text") or ""
        if not text.strip():
            continue
        blocks.append(
            f"--- Document {d['document_id']} "
            f"({d.get('doc_type', 'unknown')}, "
            f"{d.get('document_date', 'undated')}) ---\n{text}"
        )

    if not blocks:
        log.warning("llm_naive: no document text available; returning []")
        return []

    raw_corpus = "\n\n".join(blocks)

    # TODO (after gate): build_llm_naive_prompt() in agents/prompts.py
    # TODO (after gate): call Claude with naive prompt
    # TODO (after gate): parse, return — NO validation
    raise NotImplementedError(
        "llm_naive prompt + call to be finalised after extracted_text "
        "plumbing is verified. See spec review Gap 1."
    )


def _llm_only_thoughtful_pass(
    documents: list[dict],
    client: Anthropic | None = None,
) -> list[dict]:
    """
    Thoughtful LLM-only baseline. Same input as naive (raw text, no entities),
    but with a carefully written prompt: asks Claude to identify risks AND
    quote the supporting sentence from the source document.

    This is the 'fair' LLM baseline. A reviewer asking 'did you compare
    against a well-prompted LLM?' is answered by this condition.

    REQUIRES: documents must include 'extracted_text' field.
    """
    if client is None:
        client = Anthropic()

    blocks = []
    for d in documents:
        text = d.get("extracted_text") or ""
        if not text.strip():
            continue
        blocks.append(
            f"--- Document {d['document_id']} "
            f"({d.get('doc_type', 'unknown')}, "
            f"{d.get('document_date', 'undated')}) ---\n{text}"
        )

    if not blocks:
        log.warning("llm_thoughtful: no document text available; returning []")
        return []

    raw_corpus = "\n\n".join(blocks)

    # TODO (after gate): build_llm_thoughtful_prompt() in agents/prompts.py
    # TODO (after gate): call Claude with quote-anchored prompt
    # TODO (after gate): parse, return — NO validation (validation belongs to hybrid)
    raise NotImplementedError(
        "llm_thoughtful prompt + call to be finalised after extracted_text "
        "plumbing is verified. See spec review Gap 1."
    )



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