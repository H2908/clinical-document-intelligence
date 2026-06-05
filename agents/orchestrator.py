"""
LangGraph orchestrator — chains the four agents into one runnable graph.

State flows:
    read_entities  ->  timeline_agent
                  ->  flag_agent
                  ->  contradiction_agent  (depends on timeline + flags)
                  ->  briefing_agent       (depends on everything)
                  ->  write_outputs

Task 1 (this file): the graph structure + reads + writes. Each agent is
imported from agents/<name>_agent.py — for now they are thin stubs that
return empty lists. Tasks 2-5 implement them properly.
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
# Note: snowflake_reader is a new file your partner will need to write.
# For Task 1 we'll add it as a placeholder.

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
    contradictions: list[dict]
    briefing: dict | None     # one summary object, see NLP_OUTPUT.md / MART.patient_summary

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
    try:
        state["flags"] = detect_flags(
            patient_id=state["patient_id"],
            entities=state["entities"],
            documents=state["documents"],
        )
        log.info("Flags: %d found", len(state["flags"]))
    except Exception as e:
        log.exception("flag_agent failed")
        state["errors"].append(f"flag: {e}")
        state["flags"] = []
    return state


def _contradiction_node(state: OrchestrationState) -> OrchestrationState:
    try:
        state["contradictions"] = find_contradictions(
            patient_id=state["patient_id"],
            entities=state["entities"],
            documents=state["documents"],
        )
        log.info("Contradictions: %d found", len(state["contradictions"]))
    except Exception as e:
        log.exception("contradiction_agent failed")
        state["errors"].append(f"contradiction: {e}")
        state["contradictions"] = []
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

    # Imports are local to defer dependency on partner's writer module
    # until it's ready. These names match docs/DB_SCHEMA.md §6.
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
            write_flags(patient_id, state["flags"])
        except Exception as e:
            log.exception("write_flags failed")
            state["errors"].append(f"write_flags: {e}")

    if state["contradictions"]:
        try:
            write_contradictions(patient_id, state["contradictions"])
        except Exception as e:
            log.exception("write_contradictions failed")
            state["errors"].append(f"write_contradictions: {e}")

    # Always refresh the summary — even if some agents failed, the doctor
    # benefits from whatever data did land.
    try:
        refresh_summary(patient_id)
    except Exception as e:
        log.exception("refresh_summary failed")
        state["errors"].append(f"refresh_summary: {e}")

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
        Final OrchestrationState dict with all agent outputs.
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
        "contradictions": [],
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
        "errors": state["errors"],
    }, indent=2))