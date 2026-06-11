"""
LangGraph orchestrator — chains the four agents into one runnable graph.

State flows:
    read_entities  ->  timeline_agent
                  ->  flag_agent             (returns flags + metadata)
                  ->  contradiction_agent    (returns contradictions + metadata)
                  ->  briefing_agent
                  ->  write_outputs

Phase 3 + ablation switches:
    Each LLM-using agent returns (output, metadata). Metadata records
    which mode/configuration produced the output, for evaluation logging.
"""

from __future__ import annotations
import logging
from typing import TypedDict, Any

from langgraph.graph import StateGraph, START, END

from agents.timeline_agent import build_timeline
from agents.flag_agent import detect_flags
from agents.contradiction_agent import find_contradictions
from agents.briefing_agent import build_briefing
from database.snowflake_reader import (
    read_entities_for_patient,
    read_documents_for_patient,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State — the dict that flows through the graph
# ---------------------------------------------------------------------------

class OrchestrationState(TypedDict):
    """
    State carried through the LangGraph. Each agent reads what it needs
    and adds its output. The 'write' node at the end sees the full picture.
    """
    # Inputs (set before graph runs)
    patient_id: str
    document_id: str          # the document that triggered this run

    # Loaded by read_entities
    entities: list[dict]      # all entities for this patient, across all documents
    documents: list[dict]     # all document metadata for this patient

    # Filled in by each agent
    timeline_events: list[dict]
    flags: list[dict]
    flag_metadata: dict       # mode, n_rule_flags, n_llm_flags, prompt_version, etc.
    contradictions: list[dict]
    contradiction_metadata: dict  # validate_provenance, n_parsed, n_rejected, etc.
    briefing: dict | None     # see NLP_OUTPUT.md / MART.patient_summary

    # Diagnostics (optional)
    errors: list[str]


# ---------------------------------------------------------------------------
# Node: read patient state from CORE
# ---------------------------------------------------------------------------

def _read_patient_state(state: OrchestrationState) -> OrchestrationState:
    """Load all entities + documents for this patient from CORE."""
    patient_id = state["patient_id"]
    log.info("Reading patient state for %s", patient_id)
    try:
        entities = read_entities_for_patient(patient_id)
        documents = read_documents_for_patient(patient_id)
    except Exception as e:
        log.exception("Failed to read patient state")
        state["errors"].append(f"read_patient_state: {e}")
        entities, documents = [], []

    state["entities"] = entities
    state["documents"] = documents
    log.info("Loaded %d entities, %d documents", len(entities), len(documents))
    return state


# ---------------------------------------------------------------------------
# Agent nodes — each calls its agent module and updates state
# ---------------------------------------------------------------------------

def _timeline_node(state: OrchestrationState) -> OrchestrationState:
    try:
        state["timeline_events"] = build_timeline(
            entities=state["entities"],
            documents=state["documents"],
        )
        log.info("Timeline: %d events", len(state["timeline_events"]))
    except Exception as e:
        log.exception("timeline_agent failed")
        state["errors"].append(f"timeline: {e}")
        state["timeline_events"] = []
    return state


def _flag_node(state: OrchestrationState) -> OrchestrationState:
    """
    Calls flag_agent.detect_flags which now returns (flags, metadata).
    Metadata records: mode, n_rule_flags, n_llm_flags, prompt_version, etc.
    """
    try:
        flags, metadata = detect_flags(
            patient_id=state["patient_id"],
            entities=state["entities"],
            documents=state["documents"],
        )
        state["flags"] = flags
        state["flag_metadata"] = metadata
        log.info(
            "Flags: %d found (mode=%s, rule=%d, llm=%d)",
            len(flags),
            metadata.get("mode"),
            metadata.get("n_rule_flags", 0),
            metadata.get("n_llm_flags", 0),
        )
    except Exception as e:
        log.exception("flag_agent failed")
        state["errors"].append(f"flag: {e}")
        state["flags"] = []
        state["flag_metadata"] = {"error": str(e)}
    return state


def _contradiction_node(state: OrchestrationState) -> OrchestrationState:
    """
    Calls contradiction_agent.find_contradictions which now returns
    (contradictions, metadata). Metadata records: validate_provenance,
    n_parsed, n_returned, n_would_be_rejected, rejection_reasons.
    """
    try:
        contradictions, metadata = find_contradictions(
            patient_id=state["patient_id"],
            entities=state["entities"],
            documents=state["documents"],
        )
        state["contradictions"] = contradictions
        state["contradiction_metadata"] = metadata
        log.info(
            "Contradictions: %d found (validate=%s, parsed=%d, would_reject=%d)",
            len(contradictions),
            metadata.get("validate_provenance"),
            metadata.get("n_parsed", 0),
            metadata.get("n_would_be_rejected", 0),
        )
    except Exception as e:
        log.exception("contradiction_agent failed")
        state["errors"].append(f"contradiction: {e}")
        state["contradictions"] = []
        state["contradiction_metadata"] = {"error": str(e)}
    return state


def _briefing_node(state: OrchestrationState) -> OrchestrationState:
    try:
        state["briefing"] = build_briefing(
            patient_id=state["patient_id"],
            entities=state["entities"],
            documents=state["documents"],
            timeline_events=state["timeline_events"],
            flags=state["flags"],
            contradictions=state["contradictions"],
        )
        log.info("Briefing built")
    except Exception as e:
        log.exception("briefing_agent failed")
        state["errors"].append(f"briefing: {e}")
        state["briefing"] = None
    return state


# ---------------------------------------------------------------------------
# Node: write outputs to CORE + MART
# ---------------------------------------------------------------------------

def _write_outputs(state: OrchestrationState) -> OrchestrationState:
    """Write timeline, flags, contradictions, briefing to Snowflake."""
    patient_id = state["patient_id"]
    log.info("Writing outputs for %s", patient_id)

    # Imports are local to defer dependency on the writer module.
    # These names match docs/DB_SCHEMA.md §6.
    from database.snowflake_writer import (
        write_timeline,
        write_flags,
        write_contradictions,
        refresh_summary,
    )

    if state["timeline_events"]:
        try:
            write_timeline(patient_id, state["timeline_events"])
        except Exception as e:
            log.exception("write_timeline failed")
            state["errors"].append(f"write_timeline: {e}")

    if state["flags"]:
        try:
            # SP_WRITE_FLAGS expects source_document_id; v1.3 AI flags
            # emit cited_document_id. Map so both rule and AI flags persist.
            # TODO partner: update SP_WRITE_FLAGS to handle both field names.
            flags_to_write = []
            for f in state["flags"]:
                fcopy = dict(f)
                if "source_document_id" not in fcopy and "cited_document_id" in fcopy:
                    fcopy["source_document_id"] = fcopy["cited_document_id"]
                flags_to_write.append(fcopy)
            write_flags(patient_id, flags_to_write)
        except Exception as e:
            log.exception("write_flags failed")
            state["errors"].append(f"write_flags: {e}")

    if state["contradictions"]:
        try:
            write_contradictions(patient_id, state["contradictions"])
        except Exception as e:
            log.exception("write_contradictions failed")
            state["errors"].append(f"write_contradictions: {e}")

    # Persist briefing directly to MART (bypasses SP_REFRESH_SUMMARY which
    # builds from CORE.condition / CORE.medication - tables not currently
    # populated). The briefing agent's dict is the source of truth.
    if state["briefing"]:
        try:
            from database.snowflake_writer import write_briefing
            write_briefing(patient_id, state["briefing"])
        except Exception as e:
            log.exception("write_briefing failed")
            state["errors"].append(f"write_briefing: {e}")

        return state
# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph():
    """
    Build the LangGraph. Returns a compiled runnable.

    Topology:
        START -> read_patient_state -> timeline -> flag
              -> contradiction -> briefing -> write_outputs -> END
    """
    g = StateGraph(OrchestrationState)

    g.add_node("read_patient_state", _read_patient_state)
    g.add_node("timeline", _timeline_node)
    g.add_node("flag", _flag_node)
    g.add_node("contradiction", _contradiction_node)
    g.add_node("briefing", _briefing_node)
    g.add_node("write_outputs", _write_outputs)

    g.add_edge(START, "read_patient_state")
    g.add_edge("read_patient_state", "timeline")
    g.add_edge("timeline", "flag")
    g.add_edge("flag", "contradiction")
    g.add_edge("contradiction", "briefing")
    g.add_edge("briefing", "write_outputs")
    g.add_edge("write_outputs", END)

    return g.compile()


# ---------------------------------------------------------------------------
# Public API — the function the worker calls
# ---------------------------------------------------------------------------

_graph = None


def run_agents(patient_id: str, document_id: str) -> OrchestrationState:
    """
    Run the agent orchestration for one patient.

    Args:
        patient_id: which patient's state to refresh.
        document_id: the document that triggered this run (for logging only;
                     the agents see the full patient state, not just this doc).

    Returns:
        Final OrchestrationState dict with all agent outputs + metadata.
    """
    global _graph
    if _graph is None:
        _graph = build_graph()

    initial: OrchestrationState = {
        "patient_id": patient_id,
        "document_id": document_id,
        "entities": [],
        "documents": [],
        "timeline_events": [],
        "flags": [],
        "flag_metadata": {},
        "contradictions": [],
        "contradiction_metadata": {},
        "briefing": None,
        "errors": [],
    }
    return _graph.invoke(initial)


# ---------------------------------------------------------------------------
# CLI for manual testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import json
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if len(sys.argv) < 3:
        print("Usage: python -m agents.orchestrator <patient_id> <document_id>")
        sys.exit(1)

    patient_id = sys.argv[1]
    document_id = sys.argv[2]
    state = run_agents(patient_id, document_id)

    print(json.dumps({
        "patient_id": state["patient_id"],
        "document_id": state["document_id"],
        "counts": {
            "entities": len(state["entities"]),
            "documents": len(state["documents"]),
            "timeline_events": len(state["timeline_events"]),
            "flags": len(state["flags"]),
            "contradictions": len(state["contradictions"]),
            "briefing": "present" if state["briefing"] else "missing",
        },
        "flag_metadata": state.get("flag_metadata", {}),
        "contradiction_metadata": state.get("contradiction_metadata", {}),
        "errors": state["errors"],
    }, indent=2, default=str))