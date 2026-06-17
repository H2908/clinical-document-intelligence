"""Audit agent - tamper-evident flag provenance hashing.

Per Phase 4 L2 spec (locked 2026-06-17): every flag carries a SHA-256
hash of its inputs + content, computable deterministically. The hash
proves the flag was emitted exactly as recorded; any modification to
the source_quote, cited document, generation context, or flag content
fields is detectable via hash mismatch.

B2 design: hash covers both PROVENANCE (where the flag came from) AND
CONTENT (what the flag says). B1 (provenance-only) would miss downstream
edits to severity/category/description.

Hashed fields:
    Provenance:
      - source_quote      (LLM flags) - empty for rule flags
      - cited_document_id (LLM flags) - empty for rule flags
      - source_document_id (rule flags) - empty for LLM flags
      - model             (caller context)
      - prompt_version    (caller context)
      - temperature       (caller context)
    Content:
      - severity
      - category
      - clinical_subject
      - description

NOT hashed (volatile or derived):
    - flag_id (generated post-hash)
    - created_at / timestamp (varies per write)
    - status (open/resolved - mutable lifecycle field)
    - resolved_at

Canonical encoding: JSON with sorted keys, no whitespace. Makes the hash
deterministic regardless of dict iteration order.

Usage:
    from agents.audit_agent import hash_flag, verify_jsonl_run

    h = hash_flag(flag, context={"model": "claude-sonnet-4-6",
                                  "prompt_version": "v1.3",
                                  "temperature": 0.7})
    # h is a 64-char SHA-256 hex digest

    # Verify a JSONL run from the held-out evaluation:
    report = verify_jsonl_run("evaluation/results/smoke_with_subject.jsonl")
    print(report.summary())
"""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Canonical field projection - exactly what enters the hash
# ---------------------------------------------------------------------------

# Fields read from the flag dict. Missing fields become "" (empty string)
# so hashes are stable across rule vs LLM flag shapes.
FLAG_PROVENANCE_FIELDS = (
    "source_quote",
    "cited_document_id",
    "source_document_id",
)

FLAG_CONTENT_FIELDS = (
    "severity",
    "category",
    "clinical_subject",
    "description",
)

# Fields read from the caller-supplied context (row metadata).
CONTEXT_FIELDS = (
    "model",
    "prompt_version",
    "temperature",
)


def _project(flag: dict, context: dict) -> dict:
    """Build the canonical projection of a flag for hashing.

    Missing fields become "" (empty string) so the hash is stable
    regardless of which subset of fields is present on a given flag
    type (rules-only vs LLM).
    """
    out = {}
    for f in FLAG_PROVENANCE_FIELDS + FLAG_CONTENT_FIELDS:
        v = flag.get(f, "")
        # Normalise None to ""
        out[f] = "" if v is None else str(v)
    for f in CONTEXT_FIELDS:
        v = context.get(f, "")
        out[f] = "" if v is None else str(v)
    return out


def hash_flag(flag: dict, context: Optional[dict] = None) -> str:
    """Compute the SHA-256 provenance + content hash of a flag.

    Args:
        flag: a flag dict from agents/flag_agent.py or a JSONL row.
        context: optional dict with model, prompt_version, temperature.
            If omitted, those fields hash as empty strings.

    Returns:
        64-char hex SHA-256 digest.

    Deterministic: identical (flag, context) always produces the same hash.
    """
    projection = _project(flag, context or {})
    canonical = json.dumps(projection, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def attach_hash(flag: dict, context: Optional[dict] = None) -> dict:
    """Return a copy of flag with provenance_hash set. Idempotent."""
    out = dict(flag)
    out["provenance_hash"] = hash_flag(flag, context)
    return out


# ---------------------------------------------------------------------------
# Audit report types
# ---------------------------------------------------------------------------

@dataclass
class FlagAuditResult:
    flag_index: int                  # position within the run
    expected_hash: str
    stored_hash: Optional[str]       # None if pre-instrumentation
    status: str                      # "match" | "mismatch" | "no_stored_hash"
    flag_summary: str                # short text for reports


@dataclass
class RunAuditResult:
    run_id: str
    patient_id: str
    condition: str
    sampling_run: int
    n_flags: int
    n_match: int
    n_mismatch: int
    n_no_stored_hash: int
    flag_results: list[FlagAuditResult] = field(default_factory=list)


@dataclass
class JsonlAuditReport:
    path: str
    total_rows: int
    total_flags: int
    runs: list[RunAuditResult] = field(default_factory=list)

    def summary(self) -> str:
        match = sum(r.n_match for r in self.runs)
        mismatch = sum(r.n_mismatch for r in self.runs)
        no_hash = sum(r.n_no_stored_hash for r in self.runs)
        lines = [
            f"Audit report for {self.path}",
            f"  Rows:    {self.total_rows}",
            f"  Flags:   {self.total_flags}",
            f"  Match:        {match}",
            f"  Mismatch:     {mismatch}",
            f"  No stored hash: {no_hash}",
        ]
        if mismatch > 0:
            lines.append("")
            lines.append("MISMATCHES (potential tampering):")
            for r in self.runs:
                for fr in r.flag_results:
                    if fr.status == "mismatch":
                        lines.append(
                            f"  run={r.run_id[:8]} cond={r.condition} rep={r.sampling_run} "
                            f"flag#{fr.flag_index}: {fr.flag_summary}"
                        )
                        lines.append(f"    expected: {fr.expected_hash}")
                        lines.append(f"    stored:   {fr.stored_hash}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSONL verification - the round-trip integrity check
# ---------------------------------------------------------------------------

def _row_context(row: dict) -> dict:
    """Extract generation context from a JSONL row's metadata."""
    meta = row.get("metadata") or {}
    return {
        "model": row.get("model", ""),
        "prompt_version": meta.get("prompt_version") or row.get("instrument_version", ""),
        "temperature": row.get("temperature", ""),
    }


def verify_jsonl_run(path: str | Path) -> JsonlAuditReport:
    """Verify every accepted_flag in a JSONL evaluation run.

    For each row:
      1. Compute the context from row metadata (model, prompt_version, temp).
      2. For each flag in accepted_flags:
         - Compute expected hash via hash_flag(flag, context).
         - Read stored_hash from flag.get("provenance_hash").
         - If stored is None: status = "no_stored_hash" (pre-instrumentation).
         - If stored matches: status = "match".
         - Otherwise: status = "mismatch" (potential tampering).

    Returns a JsonlAuditReport.
    """
    path = Path(path)
    report = JsonlAuditReport(path=str(path), total_rows=0, total_flags=0)

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            report.total_rows += 1

            context = _row_context(row)
            run_result = RunAuditResult(
                run_id=row.get("run_id", ""),
                patient_id=row.get("patient_id", ""),
                condition=row.get("condition", ""),
                sampling_run=row.get("sampling_run", -1),
                n_flags=0,
                n_match=0,
                n_mismatch=0,
                n_no_stored_hash=0,
            )

            for i, flag in enumerate(row.get("accepted_flags", []) or []):
                if not isinstance(flag, dict):
                    continue
                report.total_flags += 1
                run_result.n_flags += 1

                expected = hash_flag(flag, context)
                stored = flag.get("provenance_hash")
                summary = (
                    f"cat={flag.get('category', '?')} "
                    f"subj={flag.get('clinical_subject', '?')!r}"
                )

                if stored is None:
                    status = "no_stored_hash"
                    run_result.n_no_stored_hash += 1
                elif stored == expected:
                    status = "match"
                    run_result.n_match += 1
                else:
                    status = "mismatch"
                    run_result.n_mismatch += 1

                run_result.flag_results.append(FlagAuditResult(
                    flag_index=i,
                    expected_hash=expected,
                    stored_hash=stored,
                    status=status,
                    flag_summary=summary,
                ))

            report.runs.append(run_result)

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Verify provenance hashes for flags in a JSONL evaluation run."
    )
    parser.add_argument(
        "--jsonl",
        required=True,
        help="Path to JSONL run file (e.g., evaluation/results/smoke_with_subject.jsonl).",
    )
    args = parser.parse_args()

    report = verify_jsonl_run(args.jsonl)
    print(report.summary())
    # Exit code: 0 if all flags match or have no stored hash, 1 on any mismatch
    any_mismatch = any(r.n_mismatch > 0 for r in report.runs)
    return 1 if any_mismatch else 0


if __name__ == "__main__":
    import sys
    sys.exit(main())