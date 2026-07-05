"""
pipeline/llm_client.py — thin wrapper around the Anthropic Claude API,
faithfully extracted from agents/flag_agent.py's _llm_second_pass.

Sampling parameters are fixed to the exact values used to produce every
result in the paper (see paper, Section 2, "Flag-identity deduplication"
and the sampling-parameters footnote): model claude-sonnet-4-6,
temperature 0.7, max_tokens 1500. These are not configurable at the
call site deliberately, so a reviewer re-running this script gets the
same operating point used throughout the paper's evaluation.

This module does not implement the four-guard grounding validation
itself — that lives in grounding.py, kept separate so the LLM-calling
code and the validation logic can be tested (and read) independently.
"""
from __future__ import annotations
import os
import re
import json
import logging
from typing import Optional

from anthropic import Anthropic

log = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
TEMPERATURE = 0.7
MAX_TOKENS = 1500

SYSTEM_FRAMING = (
    "You are a clinical safety reviewer assisting an NHS doctor reviewing "
    "a patient's chart before an appointment. You DO NOT provide medical "
    "advice — you only surface patterns the doctor should verify."
)


def _extract_json_payload(raw: str) -> str:
    """Extract a JSON payload from a raw LLM response, tolerating the
    model reasoning in prose before emitting a fenced ```json block
    despite being instructed not to (a real failure mode found and
    fixed during this paper's MTSamples generalisation testing — see
    paper, Evaluation section, 'A validator calibration bug, found and
    fixed'). Searches for a fenced block anywhere in the response, not
    just at the start."""
    raw = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def call_claude(prompt: str, client: Optional[Anthropic] = None) -> list[dict]:
    """Call Claude with the fixed sampling parameters used throughout
    the paper, and parse the response as a JSON array of proposed flags
    or contradictions.

    Returns an empty list (logged, not raised) if the response is not
    valid JSON after fence-extraction, or is not a JSON array — this
    matches the production pipeline's conservative-by-default behaviour:
    an unparseable response produces no output rather than a crash or
    a fabricated fallback.

    Requires ANTHROPIC_API_KEY to be set in the environment (e.g. via
    a local .env file, never committed — see pipeline/README.md).
    """
    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. This pipeline requires your "
                "own Anthropic API key to run live inference; it is read "
                "from the environment (e.g. a local .env file) and is "
                "never transmitted, logged, or stored by this code beyond "
                "the official Anthropic API call itself."
            )
        client = Anthropic()

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text if response.content else ""
    if getattr(response, "stop_reason", None) == "max_tokens":
        log.warning(
            "Response was truncated by hitting max_tokens=%d before completion "
            "(stop_reason=max_tokens). The JSON is likely incomplete.", MAX_TOKENS
        )
    payload = _extract_json_payload(raw)

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        log.warning("LLM response was not valid JSON after fence-extraction; returning []")
        log.warning("--- RAW RESPONSE (first 2000 chars) ---")
        log.warning("%s", raw[:2000])
        log.warning("--- EXTRACTED PAYLOAD (first 2000 chars) ---")
        log.warning("%s", payload[:2000])
        log.warning("--- END ---")
        return []

    if not isinstance(parsed, list):
        log.warning("LLM response was valid JSON but not a list; returning []")
        return []

    return parsed


def build_flag_proposal_prompt(entity_summary: list[dict], existing_flags: list[dict]) -> str:
    """Build the prompt for proposing additional safety flags beyond
    what the deterministic rule layer caught. This is a simplified,
    standalone version of agents/prompts.py's build_flag_second_pass,
    sufficient for this reproducibility script; the exact production
    prompt template (with its full good/bad quoting examples) is
    documented verbatim in pipeline/PROMPTS.md for exact reproduction.

    Includes an explicit flag-count cap and conciseness instruction,
    matching the real production prompts (which cap at 8 flags with
    one-sentence descriptions) — found necessary after this standalone
    prompt's first version omitted the cap and produced a response that
    exceeded max_tokens=1500 mid-generation on a document with many
    extractable entities, yielding truncated, unparseable JSON.
    """
    return f"""{SYSTEM_FRAMING}

PATIENT ENTITIES (extracted from documents):
{json.dumps(entity_summary, indent=2, default=str)}

EXISTING RULE-BASED FLAGS (already caught, do not repeat):
{json.dumps(existing_flags, indent=2, default=str)}

INSTRUCTIONS:
1. Output ONLY a JSON array of flag objects. No prose, no markdown fences.
2. Each flag MUST have exactly these seven fields:
   - "severity": "HIGH" | "MEDIUM" | "LOW"
   - "category": short code, e.g. "AI_DRUG_INTERACTION"
   - "description": ONE concise sentence, natural language for the doctor
   - "clinical_subject": canonical short noun phrase (e.g. "metformin in renal failure")
   - "cited_document_id": must be one of the document IDs in the entities above
   - "source_quote": a VERBATIM excerpt from the cited document, not a paraphrase
     and not a combination of text from multiple locations
   - "grounding_status": leave as null; this is filled in by post-generation validation
3. Maximum 5 flags. Propose only the most clinically significant findings,
   not every possible observation — prioritise quality and concision over
   exhaustiveness, and keep each description to a single sentence.

GOOD source_quote (verbatim, complete, grounds the flag):
  "Repeat echocardiogram in 6 months"

BAD source_quote (stitches words from non-adjacent parts of the document):
  "NYHA class II consistent with heart failure therapy"
  (when the document actually says "...symptoms consistent with NYHA class II"
  in one sentence and "...Continue current heart failure therapy" in another)

If you find no additional risks beyond the existing flags, return [].

OUTPUT (JSON array only, maximum 5 flags, one concise sentence each):"""