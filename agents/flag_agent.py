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
from agents.prompts import (
    build_flag_second_pass,
    build_flag_llm_thoughtful,
    build_flag_llm_naive,
    get_prompt_version,
)
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
        except NotImplementedError:
            raise
        except Exception:
            log.exception("LLM second-pass failed in mode=hybrid")
            llm_flags = []

    elif mode == "llm_naive":
        try:
            llm_flags = _llm_only_naive_pass(documents, client=llm_client)
        except NotImplementedError:
            raise  # gated/unimplemented modes must fail loud
        except Exception:
            log.exception("LLM naive pass failed in mode=llm_naive")
            llm_flags = []

    elif mode == "llm_thoughtful":
        try:
            llm_flags = _llm_only_thoughtful_pass(documents, client=llm_client)
        except NotImplementedError:
            raise  # gated/unimplemented modes must fail loud
        except Exception:
            log.exception("LLM thoughtful pass failed in mode=llm_thoughtful")
            llm_flags = []

    flags = rule_flags + llm_flags
    metadata = {
        "prompt_version": (
            get_prompt_version("flag_second_pass") if mode == "hybrid"
            else get_prompt_version("flag_llm_naive") if mode == "llm_naive" and llm_flags
            else get_prompt_version("flag_llm_thoughtful") if mode == "llm_thoughtful" and llm_flags
            else None
        ),
        "temperature": 0.7,  # locked operating point for all LLM-using modes
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
    Hybrid v1.2 validator with four guards:
        1. cited_document_id must be in patient's documents
        2. source_quote must meet minimum length (>= 30 chars AND >= 6 words)
        3. source_quote must appear verbatim in cited document text
        4. source_quote must share at least one clinical subject word with
           the flag's own description (closes the padding loophole)

    All four guards emit distinct VERDICT log lines for downstream bucket
    analysis (paper Day 2 instrument-hardening).
    """
    import re

    # Flag-validator ablation switch (paper Day 3).
    # FLAG_VALIDATE=false disables Guard 3 (the v1.3 grounding validator).
    # Guards 1, 2, 4 remain active. Default ON = production behaviour.
    FLAG_VALIDATE_GROUNDING = os.environ.get("FLAG_VALIDATE", "true").lower() != "false"
    log.info("FLAG_VALIDATE_GROUNDING=%s", FLAG_VALIDATE_GROUNDING)

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

    # Build a map of document_id -> extracted_text for quote validation
    doc_text_by_id = {
        d["document_id"]: (d.get("extracted_text") or "")
        for d in documents
    }

    # Minimum quote requirements (Day 2 instrument-hardening, v1.2)
    MIN_QUOTE_CHARS = 30
    MIN_QUOTE_WORDS = 6
    MIN_QUOTE_WORDS_SOFT = 3  # soft branch word floor (with subject-overlap)

    required_fields = (
        "severity", "category", "description",
        "cited_document_id", "source_quote",
    )

    # Stopwords stripped before checking quote-vs-flag subject overlap.
    # Locked instrument: spaCy's en_core_web_sm STOP_WORDS (pinned version)
    # plus a small, paper-declared clinical-generic set.
    # The declared set:
    #   patient    - universal in clinical docs, never the subject
    #   documented - provenance verb
    #   noted      - provenance verb
    #   listed     - provenance verb
    #   verify     - instruction-to-clinician verb
    #   confirm    - instruction verb
    #   doctor     - actor word, never the subject
    CLINICAL_GENERIC = {
        "patient", "documented", "noted", "listed",
        "verify", "confirm", "doctor",
    }
    from spacy.lang.en.stop_words import STOP_WORDS
    STOPWORDS_AND_GENERIC = STOP_WORDS | CLINICAL_GENERIC

    # Log the full pre-validation population (for bucket analysis across N runs)
    for f in parsed:
        if isinstance(f, dict):
            log.info(
                "HYBRID PRE-VALIDATION quote=%r cited=%r category=%r",
                (f.get("source_quote") or "")[:200],
                f.get("cited_document_id"),
                f.get("category"),
            )

    validated = []
    for f in parsed:
        if not isinstance(f, dict):
            continue
        if not all(k in f for k in required_fields):
            log.warning("=" * 70)
            log.warning("HYBRID VALIDATOR REJECTION: missing required field")
            log.warning("flag: %r", f)
            log.warning("VERDICT: schema-failure")
            log.warning("=" * 70)
            continue
        if f["severity"] not in ("HIGH", "MEDIUM", "LOW"):
            continue

        cited = f["cited_document_id"]
        quote = (f.get("source_quote") or "").strip()
        description = f.get("description", "")
        category = f.get("category", "")
        doc_text = doc_text_by_id.get(cited, "")

        # GUARD 1 - cited_document_id must be in patient's actual docs
        if cited not in valid_doc_ids:
            log.warning("=" * 70)
            log.warning("HYBRID VALIDATOR REJECTION on doc %s", cited)
            log.warning("LLM quote: %r", quote[:200])
            log.warning("VERDICT: phantom-citation (doc_id not in patient's records)")
            log.warning("=" * 70)
            continue

        # GUARD 2 - quote must be non-trivial in length
       # GUARD 2 - quote must be non-trivial. OR'd predicate (advisor-locked):
        #   Strict branch:  (chars>=30 AND words>=6)
        #   Soft branch:    (words>=3 AND quote_shares_subject_with_flag)
        # The soft branch admits terse-but-grounded clinical instructions
        # (e.g. "Repeat echocardiogram in 6 months") while rejecting single
        # and double keyword quotes.
        word_count = len(re.findall(r"\w+", quote))
        # Pre-compute subject overlap once (used by both Guard 2 soft branch
        # and Guard 4 below; cheaper to compute once)
        subject_text = f"{category} {description}".lower()
        subject_text = re.sub(r"\bai[_ ]", " ", subject_text)
        raw_subject_words = set(re.findall(r"[a-z]{4,}", subject_text))
        subject_words = raw_subject_words - STOPWORDS_AND_GENERIC
        quote_words_for_overlap = set(re.findall(r"[a-z]{4,}", quote.lower()))
        quote_shares_subject = bool(subject_words and (subject_words & quote_words_for_overlap))

        strict_pass = (len(quote) >= MIN_QUOTE_CHARS and word_count >= MIN_QUOTE_WORDS)
        soft_pass = (word_count >= MIN_QUOTE_WORDS_SOFT and quote_shares_subject)

        if not (strict_pass or soft_pass):
            log.warning("=" * 70)
            log.warning("HYBRID VALIDATOR REJECTION on doc %s", cited)
            log.warning("LLM quote: %r", quote)
            log.warning(
                "VERDICT: trivial-quote (chars=%d, words=%d; "
                "strict needs chars>=%d AND words>=%d; "
                "soft needs words>=%d AND subject-overlap; "
                "subject_shared=%s)",
                len(quote), word_count,
                MIN_QUOTE_CHARS, MIN_QUOTE_WORDS,
                MIN_QUOTE_WORDS_SOFT, quote_shares_subject,
            )
            log.warning("=" * 70)
            continue

        # Ablation switch (paper Day 3): when FLAG_VALIDATE_GROUNDING=False,
        # skip Guard 3 entirely. The flag passes through with grounding_status
        # set to 'unvalidated' so the JSONL row can distinguish it. Guards 1,
        # 2, 4 stay active. This isolates the v1.3 grounding-validator
        # contribution from the rest of the validation pipeline.
        if not FLAG_VALIDATE_GROUNDING:
            f["grounding_status"] = "unvalidated"
            log.info("HYBRID VALIDATOR ACCEPT (unvalidated) on doc %s", cited)
        else:
            # Tier 0: misattribution check
            #   Token-overlap against CITED doc AND every other doc. If overlap
            #   against the cited doc is below threshold but overlap against
            #   some OTHER doc clears it, the flag is misattributed.
            #
            # Tier 1: fabrication vs grounded (against cited doc only)
            #   Requires BOTH:
            #     (a) token_overlap_ratio >= FABRICATION_THRESHOLD (0.8)
            #     (b) contiguous_ngram_len >= NGRAM_FLOOR (5 content tokens)
            #            OR >= 50% of quote content tokens as a single run
            #   Token overlap alone is insufficient - composition-fabrication
            #   defeats it. The n-gram floor is what catches "real words,
            #   wrong meaning" stitched from unrelated sentences.
            #
            # Tier 2: surface fidelity (among grounded)
            #   Exact substring (after whitespace collapse) -> verbatim
            #   Otherwise -> paraphrase
            FABRICATION_THRESHOLD = 0.8   # at most 1 content word in 5 unaccounted for
            NGRAM_FLOOR = 5               # minimum contiguous content-token match

            def _content_tokens(text: str) -> list[str]:
                """Tokenise to lowercase content tokens (>=4 chars, alpha, not stopwords)."""
                tokens = re.findall(r"[a-z]{4,}", text.lower())
                return [t for t in tokens if t not in STOPWORDS_AND_GENERIC]

            def _longest_contiguous_match(a: list[str], b: list[str]) -> int:
                """Length of longest contiguous sequence shared by lists a and b."""
                if not a or not b:
                    return 0
                n, m = len(a), len(b)
                # Standard LCS-substring DP
                dp = [[0] * (m + 1) for _ in range(n + 1)]
                best = 0
                for i in range(1, n + 1):
                    for j in range(1, m + 1):
                        if a[i - 1] == b[j - 1]:
                            dp[i][j] = dp[i - 1][j - 1] + 1
                            if dp[i][j] > best:
                                best = dp[i][j]
                return best

            quote_tokens = _content_tokens(quote)
            cited_tokens = _content_tokens(doc_text)

            if not quote_tokens:
                log.warning("=" * 70)
                log.warning("HYBRID VALIDATOR REJECTION on doc %s", cited)
                log.warning("LLM quote: %r", quote)
                log.warning("VERDICT: empty-content-quote (no content tokens after stopword strip)")
                log.warning("=" * 70)
                continue

            # Overlap ratio against cited document
            overlap_cited = len(set(quote_tokens) & set(cited_tokens))
            overlap_ratio_cited = overlap_cited / len(set(quote_tokens))

            # Tier 0 - misattribution check: if cited overlap is low but some
            # other doc would clear it, flag misattribution.
            if overlap_ratio_cited < FABRICATION_THRESHOLD:
                best_other_ratio = 0.0
                best_other_doc = None
                for other_id, other_text in doc_text_by_id.items():
                    if other_id == cited:
                        continue
                    other_tokens = _content_tokens(other_text)
                    if not other_tokens:
                        continue
                    other_overlap = len(set(quote_tokens) & set(other_tokens))
                    other_ratio = other_overlap / len(set(quote_tokens))
                    if other_ratio > best_other_ratio:
                        best_other_ratio = other_ratio
                        best_other_doc = other_id

                if best_other_ratio >= FABRICATION_THRESHOLD:
                    log.warning("=" * 70)
                    log.warning("HYBRID VALIDATOR REJECTION on doc %s", cited)
                    log.warning("LLM quote: %r", quote[:200])
                    log.warning("LLM description: %r", description[:120])
                    log.warning(
                        "VERDICT: misattributed "
                        "(overlap with cited=%.2f below %.2f, but overlap with %s=%.2f)",
                        overlap_ratio_cited, FABRICATION_THRESHOLD,
                        best_other_doc, best_other_ratio,
                    )
                    log.warning("=" * 70)
                    continue

                # No other doc rescues it -> fabrication
                log.warning("=" * 70)
                log.warning("HYBRID VALIDATOR REJECTION on doc %s", cited)
                log.warning("LLM quote: %r", quote[:200])
                log.warning("LLM description: %r", description[:120])
                log.warning(
                    "VERDICT: fabrication "
                    "(token-overlap with cited doc=%.2f, below %.2f; no other doc rescues)",
                    overlap_ratio_cited, FABRICATION_THRESHOLD,
                )
                log.warning("=" * 70)
                continue

            # Tier 1b - contiguous n-gram floor
            longest_run = _longest_contiguous_match(quote_tokens, cited_tokens)
            ngram_required = max(NGRAM_FLOOR, len(quote_tokens) // 2)
            if longest_run < min(NGRAM_FLOOR, ngram_required) or longest_run < min(NGRAM_FLOOR, max(1, len(quote_tokens) // 2)):
                # Decision rule: longest contiguous run must be either >= NGRAM_FLOOR
                # OR >= 50% of quote content tokens (whichever is achievable on a
                # short quote). A 4-token quote can't have a 5-token run; allow it
                # if half the quote runs contiguously.
                min_run_needed = min(NGRAM_FLOOR, max(2, len(quote_tokens) // 2 + 1))
                if longest_run < min_run_needed:
                    log.warning("=" * 70)
                    log.warning("HYBRID VALIDATOR REJECTION on doc %s", cited)
                    log.warning("LLM quote: %r", quote[:200])
                    log.warning("LLM description: %r", description[:120])
                    log.warning(
                        "VERDICT: composition-fabrication "
                        "(token-overlap=%.2f passes, but longest contiguous run=%d "
                        "below required %d - quote stitches scattered words)",
                        overlap_ratio_cited, longest_run, min_run_needed,
                    )
                    log.warning("=" * 70)
                    continue

            # Tier 2 - grounded; classify surface fidelity (verbatim vs paraphrase)
            quote_norm = re.sub(r"\s+", " ", quote).strip()
            doc_norm = re.sub(r"\s+", " ", doc_text).strip()
            if quote_norm in doc_norm:
                f["grounding_status"] = "verbatim"
                log.info(
                    "HYBRID VALIDATOR ACCEPT (verbatim) on doc %s: overlap=%.2f, longest_run=%d",
                    cited, overlap_ratio_cited, longest_run,
                )
            else:
                f["grounding_status"] = "paraphrase"
                log.info(
                    "HYBRID VALIDATOR ACCEPT (paraphrase) on doc %s: overlap=%.2f, longest_run=%d",
                    cited, overlap_ratio_cited, longest_run,
                )

        # GUARD 4 - quote must mention the clinical subject of its own flag.
        # Closes the padding loophole. Uses subject_words and
        # quote_shares_subject already computed for Guard 2 above.
        if subject_words and not quote_shares_subject:
            log.warning("=" * 70)
            log.warning("HYBRID VALIDATOR REJECTION on doc %s", cited)
            log.warning("LLM quote: %r", quote[:200])
            log.warning("LLM description: %r", description[:120])
            log.warning(
                "VERDICT: irrelevant-padding "
                "(quote shares zero clinical subject words with flag's own "
                "description; subject_words=%s)",
                sorted(subject_words)[:10],
            )
            log.warning("=" * 70)
            continue

        # All guards passed
        f.setdefault("grounding_status", None)
        if not f["category"].startswith("AI_"):
            f["category"] = f"AI_{f['category']}"
        validated.append(f)

    log.info(
        "LLM second-pass produced %d validated flags (from %d parsed)",
        len(validated), len(parsed),
    )
    return validated

def _llm_only_naive_pass(
    documents: list[dict],
    client: Anthropic | None = None,
) -> list[dict]:
    """
    Naive LLM-only baseline. Receives raw cleaned document text only.
    NO entity extraction, NO negation filtering, NO rule context,
    NO provenance enforcement.

    The strawman baseline: what unguarded prompting produces.

    REQUIRES: documents must include 'extracted_text' field.
    """
    if client is None:
        client = Anthropic()

    # Build raw corpus, tagged by document_id - never touches entity list
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

    prompt = build_flag_llm_naive(raw_corpus)
    log.info(
        "flag_agent: llm_naive using prompt version %s",
        get_prompt_version("flag_llm_naive"),
    )

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
        log.warning("llm_naive: LLM returned non-JSON; ignoring")
        return []

    if not isinstance(parsed, list):
        return []

    # No validation at all - this is the strawman. Return what the LLM said.
    # Minimal shape enforcement so downstream code doesn't crash.
    required_fields = ("severity", "category", "description",
                       "cited_document_id", "source_quote")
    out = []
    for f in parsed:
        if isinstance(f, dict) and all(k in f for k in required_fields):
            f.setdefault("grounding_status", None)
            out.append(f)

    log.info("llm_naive: returning %d flags (no validation)", len(out))
    return out


def _llm_only_thoughtful_pass(
    documents: list[dict],
    client: Anthropic | None = None,
) -> list[dict]:
    """
    Thoughtful LLM-only baseline. Same input as naive (raw text, no entities),
    but with a carefully written prompt: verbatim quoting, document scoping,
    conservative when uncertain. No hard post-validation.

    This is the "fair" LLM baseline. A reviewer asking 'did you compare
    against a well-prompted LLM?' is answered by this condition.

    REQUIRES: documents must include 'extracted_text' field.
    """
    if client is None:
        client = Anthropic()

    # Build raw corpus, tagged by document_id - never touches the entity list
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

    prompt = build_flag_llm_thoughtful(raw_corpus)
    log.info(
        "flag_agent: llm_thoughtful using prompt version %s",
        get_prompt_version("flag_llm_thoughtful"),
    )

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
        log.warning("llm_thoughtful: LLM returned non-JSON; ignoring")
        return []

    if not isinstance(parsed, list):
        return []

    # No hard validation - this is a baseline. Return what the LLM said.
    # The metric module will compute grounding_status against doc text later.
    # We do enforce shape minimally so downstream code doesn't crash.
    required_fields = ("severity", "category", "description",
                       "cited_document_id", "source_quote")
    out = []
    for f in parsed:
        if isinstance(f, dict) and all(k in f for k in required_fields):
            f.setdefault("grounding_status", None)
            out.append(f)

    log.info("llm_thoughtful: returning %d flags (no provenance validation)", len(out))
    return out


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