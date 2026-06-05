"""
Snowflake reader — reads patient state from CORE for the agent orchestrator.

Owner: DE member.
Used by: agents/orchestrator.py

Task 1 contract: two functions exposing the patient's full state.
"""
from __future__ import annotations


def read_entities_for_patient(patient_id: str) -> list[dict]:
    """
    Return every entity for this patient, across all documents.

    Each dict has the NLP_OUTPUT.md §3 shape, plus 'document_id' and
    'document_date' joined from the document row.

    STUB — partner implements via a single SELECT against CORE.entity
    joined to CORE.document.
    """
    raise NotImplementedError("DE owner — see DB_SCHEMA.md §7")


def read_documents_for_patient(patient_id: str) -> list[dict]:
    """
    Return every document for this patient, ordered by document_date DESC.

    Each dict: {document_id, doc_type, document_date, source, status}.

    STUB — partner implements via SELECT against CORE.document.
    """
    raise NotImplementedError("DE owner — see DB_SCHEMA.md §7")