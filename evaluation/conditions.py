"""
Five named conditions for the AAAI evaluation harness.

Each condition is a callable: condition_fn(patient_id, entities, documents) -> (flags, metadata)

The conditions match the FLAG_AGENT_MODE + FLAG_VALIDATE env-var combinations
already wired into agents/flag_agent.py. This module is the canonical place
where condition-name -> env-var-tuple is defined; runner.py imports from here.

The five conditions (per AAAI plan):
    RULES_ONLY          - deterministic rules only. Zero LLM calls. Perfect reproducibility.
    LLM_NAIVE           - LLM-only, raw doc text, naive prompt. Strawman upper bound.
    LLM_THOUGHTFUL      - LLM-only, careful prompt. Fair LLM baseline.
    HYBRID_VALIDATED    - rules + LLM second-pass + Guard 3 (v1.3) ON. THE SYSTEM.
    HYBRID_UNVALIDATED  - rules + LLM second-pass + Guard 3 (v1.3) OFF. Ablation.
"""
import os
from typing import Callable

from agents.flag_agent import detect_flags


# ---------------------------------------------------------------------------
# Canonical condition names (used as keys in JSONL output, paper tables, etc.)
# ---------------------------------------------------------------------------
RULES_ONLY         = "rules_only"
LLM_NAIVE          = "llm_naive"
LLM_THOUGHTFUL     = "llm_thoughtful"
HYBRID_VALIDATED   = "hybrid_validated"
HYBRID_UNVALIDATED = "hybrid_unvalidated"

ALL_CONDITIONS = (
    RULES_ONLY,
    LLM_NAIVE,
    LLM_THOUGHTFUL,
    HYBRID_VALIDATED,
    HYBRID_UNVALIDATED,
)

# Conditions where running multiple reps adds no information.
# rules_only is deterministic by construction.
DETERMINISTIC_CONDITIONS = frozenset({RULES_ONLY})


# ---------------------------------------------------------------------------
# Env-var binding per condition
# ---------------------------------------------------------------------------
# Internally, all five conditions reduce to a (FLAG_AGENT_MODE, FLAG_VALIDATE)
# tuple. This dict is the single source of truth for that mapping.
CONDITION_ENV: dict[str, dict[str, str]] = {
    RULES_ONLY:         {"FLAG_AGENT_MODE": "rules_only",     "FLAG_VALIDATE": "true"},
    LLM_NAIVE:          {"FLAG_AGENT_MODE": "llm_naive",      "FLAG_VALIDATE": "true"},
    LLM_THOUGHTFUL:     {"FLAG_AGENT_MODE": "llm_thoughtful", "FLAG_VALIDATE": "true"},
    HYBRID_VALIDATED:   {"FLAG_AGENT_MODE": "hybrid",         "FLAG_VALIDATE": "true"},
    HYBRID_UNVALIDATED: {"FLAG_AGENT_MODE": "hybrid",         "FLAG_VALIDATE": "false"},
}


def apply_condition_env(condition: str) -> dict[str, str]:
    """Set the env vars for one condition. Returns the snapshot applied."""
    if condition not in CONDITION_ENV:
        raise ValueError(
            f"Unknown condition: {condition!r}. "
            f"Must be one of {sorted(CONDITION_ENV.keys())}"
        )
    env = CONDITION_ENV[condition]
    for k, v in env.items():
        os.environ[k] = v
    return env


def clear_condition_env() -> None:
    """Remove condition-related env vars from the process."""
    for k in ("FLAG_AGENT_MODE", "FLAG_VALIDATE"):
        os.environ.pop(k, None)


# ---------------------------------------------------------------------------
# Condition callables: condition_fn(patient_id, entities, documents) -> (flags, metadata)
# ---------------------------------------------------------------------------
def run_condition(
    condition: str,
    patient_id: str,
    entities: list[dict],
    documents: list[dict],
) -> tuple[list[dict], dict]:
    """Execute one condition for one patient.

    Sets env vars per condition, calls detect_flags(), clears env vars,
    returns (flags, metadata). The caller is responsible for capturing logs
    around this call if rejection-trace data is wanted.
    """
    apply_condition_env(condition)
    try:
        flags, metadata = detect_flags(patient_id, entities, documents)
    finally:
        clear_condition_env()
    metadata = dict(metadata)
    metadata["condition"] = condition
    return flags, metadata


# Public callable map. Each entry binds a condition name to its specific runner.
CONDITION_CALLABLES: dict[str, Callable[[str, list[dict], list[dict]], tuple[list[dict], dict]]] = {
    name: (lambda p, e, d, _c=name: run_condition(_c, p, e, d))
    for name in ALL_CONDITIONS
}


def is_deterministic(condition: str) -> bool:
    """True if running the condition multiple times produces identical output."""
    return condition in DETERMINISTIC_CONDITIONS


def effective_reps(condition: str, requested_reps: int) -> int:
    """Return the number of reps actually needed for a condition.

    Deterministic conditions always return 1; non-deterministic return requested_reps.
    """
    return 1 if is_deterministic(condition) else requested_reps