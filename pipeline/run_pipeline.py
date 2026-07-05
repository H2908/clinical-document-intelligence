#!/usr/bin/env python3
"""
pipeline/run_pipeline.py — end-to-end reproducibility script.

Runs the full standalone pipeline on a single PDF: extraction (PDF ->
typed, negated entities) -> LLM flag proposal -> four-guard grounding
validation -> JSON output.

This exists so a reviewer can independently verify the paper's central
claim — that the four-guard validator (Guard 3 in particular) correctly
grounds or rejects LLM-proposed flags — on a real document, not just on
the pre-computed fixtures served by the public demo's static viewer.

Usage:
    python run_pipeline.py --input path/to/document.pdf --output results/output.json

Requires ANTHROPIC_API_KEY in the environment (e.g. via a local .env
file — see README.md in this directory for exact setup and the scope
disclaimer on what this script has and has not been validated against).
"""
from __future__ import annotations
import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from extraction import extract_from_pdf
from llm_client import call_claude, build_flag_proposal_prompt
from grounding import run_four_guards

log = logging.getLogger(__name__)


def run(input_path: str, output_path: str) -> dict:
    """Run the full pipeline on one PDF and write a JSON result file.

    Returns the result dict (also written to output_path) for
    programmatic use / testing.
    """
    load_dotenv()

    log.info("Extracting entities from %s", input_path)
    extraction_result = extract_from_pdf(input_path)
    entities = extraction_result["entities"]
    extracted_text = extraction_result["extracted_text"]
    log.info("Extracted %d entities", len(entities))

    # Filter to non-negated entities for the LLM prompt, matching the
    # production pipeline's behaviour (negated findings should not be
    # treated as positive clinical facts).
    active_entities = [e for e in entities if not e.get("negated")]

    entity_summary = [
        {
            "type": e.get("entity_type"),
            "text": e.get("text"),
            "doc": "input_document",
        }
        for e in active_entities
    ]

    log.info("Proposing flags via LLM (this requires a live API call)")
    prompt = build_flag_proposal_prompt(entity_summary, existing_flags=[])
    proposed_flags = call_claude(prompt)
    log.info("LLM proposed %d candidate flags", len(proposed_flags))

    valid_document_ids = {"input_document"}
    document_texts = {"input_document": extracted_text}

    accepted_flags = []
    rejected_flags = []
    for flag in proposed_flags:
        # Normalise the LLM's cited_document_id to match this single-document
        # run, since the prompt only ever shows it one document.
        flag["cited_document_id"] = "input_document"
        verdict = run_four_guards(
            flag,
            cited_document_text=extracted_text,
            valid_document_ids=valid_document_ids,
            other_documents=None,
        )
        flag["passed_guards"] = verdict["accepted"]
        flag["failed_guard"] = verdict["failed_guard"]
        flag["grounding_verdict"] = verdict["verdict"]
        if verdict["accepted"]:
            accepted_flags.append(flag)
        else:
            rejected_flags.append(flag)

    log.info(
        "Grounding validation: %d accepted, %d rejected",
        len(accepted_flags), len(rejected_flags),
    )

    result = {
        "input_file": str(input_path),
        "extracted_text_length": len(extracted_text),
        "entities": entities,
        "flags": {
            "accepted": accepted_flags,
            "rejected": rejected_flags,
        },
        "contradictions": [],  # not implemented in this standalone script;
                                 # see README.md scope disclaimer
    }

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    log.info("Wrote result to %s", out_path)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Run the full clinical document intelligence pipeline on one PDF."
    )
    parser.add_argument("--input", required=True, help="Path to the input PDF")
    parser.add_argument("--output", required=True, help="Path to write the output JSON")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable INFO-level logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    try:
        result = run(args.input, args.output)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Entities extracted: {len(result['entities'])}")
    print(f"Flags accepted (grounded): {len(result['flags']['accepted'])}")
    print(f"Flags rejected: {len(result['flags']['rejected'])}")
    print(f"Full output written to: {args.output}")


if __name__ == "__main__":
    main()
