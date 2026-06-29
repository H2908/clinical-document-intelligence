"""
Snowflake reader — reads patient state from CORE for the agent orchestrator
and identity state from IDENTITY for the auth layer.

Owner: DE member (this file drafted by ML, needs DE review for column-name
       alignment with the actual schema).
Used by: agents/orchestrator.py, api/routes/auth.py

Contract: see docs/DB_SCHEMA.md §7 (CORE) and CONTRACT.md §1.4 (IDENTITY).
"""

from __future__ import annotations
import os
import logging
from typing import Any

import snowflake.connector
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection helper — mirrors snowflake_writer._get_connection style
# ---------------------------------------------------------------------------

def _get_connection():
    """Build a Snowflake connection from env vars. Schema='core' for reads."""
    return snowflake.connector.connect(
        account   = os.environ["SNOWFLAKE_ACCOUNT"],
        user      = os.environ["SNOWFLAKE_USER"],
        password  = os.environ["SNOWFLAKE_PASSWORD"],
        database  = "clinical_db",
        schema    = "core",
        warehouse = "clinical_wh",
        role      = os.environ["SNOWFLAKE_ROLE"],
    )


def _rows_to_dicts(cursor) -> list[dict[str, Any]]:
    """Convert a cursor result into a list of dicts keyed by column name."""
    cols = [c[0].lower() for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_entities_for_patient(patient_id: str) -> list[dict[str, Any]]:
    """
    Return every entity for this patient, joined with its document metadata.

    Each dict matches NLP_OUTPUT.md §3 plus joined document fields:
        entity_type, text, start_offset, end_offset, negated,
        icd10_code, normalised_value,
        document_id, document_date, doc_type

    See DB_SCHEMA.md §7.1.
    """
    log.info("Reading entities for patient %s", patient_id)
    conn = _get_connection()
    try:
        cur = conn.cursor()
        # NOTE for DE reviewer: column names below assume the schema in
        # database/schemas/02_core.sql. Adjust if your column names differ
        # (e.g. start_offset vs start_char).
        cur.execute("""
            SELECT
                e.entity_type,
                e.text,
                e.start_offset,
                e.end_offset,
                e.negated,
                e.icd10_code,
                e.bnf_code,
                e.normalised_value,
                e.document_id,
                d.document_date,
                d.doc_type
            FROM clinical_db.core.entity e
            JOIN clinical_db.core.document d
              ON e.document_id = d.document_id
            WHERE d.patient_id = %s
            ORDER BY d.document_date DESC, e.start_offset ASC
        """, (patient_id,))
        rows = _rows_to_dicts(cur)
        log.info("Found %d entities for %s", len(rows), patient_id)
        return rows
    except Exception as e:
        log.exception("read_entities_for_patient failed for %s", patient_id)
        raise RuntimeError(f"read_entities_for_patient failed: {e}") from e
    finally:
        conn.close()


def read_documents_for_patient(patient_id: str) -> list[dict[str, Any]]:
    """
    Return every document for this patient, ordered newest first.

    Each dict: {document_id, doc_type, document_date, source, status,
                file_name, s3_key, uploaded_at}.

    See DB_SCHEMA.md §7.2.
    """
    log.info("Reading documents for patient %s", patient_id)
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                document_id,
                doc_type,
                document_date,
                source,
                status,
                file_name,
                s3_key,
                created_at,
                extracted_text
            FROM clinical_db.core.document
            WHERE patient_id = %s
            ORDER BY document_date DESC, created_at DESC
        """, (patient_id,))
        rows = _rows_to_dicts(cur)
        log.info("Found %d documents for %s", len(rows), patient_id)
        return rows
    except Exception as e:
        log.exception("read_documents_for_patient failed for %s", patient_id)
        raise RuntimeError(f"read_documents_for_patient failed: {e}") from e
    finally:
        conn.close()


def read_observations_for_patient(patient_id: str) -> list[dict[str, Any]]:
    """
    Return every observation for this patient, ordered newest first.

    Each dict: {observation_id, test, value, unit, observation_date,
                source_document_id, created_at}.

    Used by the FHIR builder to assemble Observation resources for
    inclusion in the patient Bundle.
    """
    log.info("Reading observations for patient %s", patient_id)
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                observation_id,
                test,
                value,
                unit,
                observation_date,
                source_document_id,
                created_at
            FROM clinical_db.core.observation
            WHERE patient_id = %s
            ORDER BY observation_date DESC NULLS LAST, created_at DESC
        """, (patient_id,))
        rows = _rows_to_dicts(cur)
        log.info("Found %d observations for %s", len(rows), patient_id)
        return rows
    except Exception as e:
        log.exception("read_observations_for_patient failed for %s", patient_id)
        raise RuntimeError(f"read_observations_for_patient failed: {e}") from e
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Identity layer reads (Problem 1 — landing/login/register PR)
# ---------------------------------------------------------------------------

def _identity_conn():
    """Connection scoped to identity schema."""
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        database="clinical_db",
        schema="identity",
        warehouse="clinical_wh",
        role=os.environ["SNOWFLAKE_ROLE"],
    )


def get_user_by_id(user_id: str) -> dict | None:
    """Return {user_id, tenant_id, email, display_name, role, created_at}
    or None when no row matches."""
    log.info("get_user_by_id: %s", user_id)
    conn = _identity_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            select user_id, tenant_id, email, display_name, role, created_at
            from clinical_db.identity.users
            where user_id = %s
            limit 1
            """,
            (user_id,),
        )
        rows = _rows_to_dicts(cur)
        return rows[0] if rows else None
    except Exception as e:
        log.exception("get_user_by_id failed for %s", user_id)
        raise RuntimeError(f"get_user_by_id failed: {e}") from e
    finally:
        conn.close()


def get_tenant_by_slug(slug: str) -> dict | None:
    """Return {tenant_id, slug, name} or None."""
    log.info("get_tenant_by_slug: %s", slug)
    conn = _identity_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "select tenant_id, slug, name from clinical_db.identity.tenants "
            "where slug = %s limit 1",
            (slug,),
        )
        rows = _rows_to_dicts(cur)
        return rows[0] if rows else None
    except Exception as e:
        log.exception("get_tenant_by_slug failed for %s", slug)
        raise RuntimeError(f"get_tenant_by_slug failed: {e}") from e
    finally:
        conn.close()


def get_tenant_by_id(tenant_id: str) -> dict | None:
    """Return {tenant_id, slug, name} or None."""
    log.info("get_tenant_by_id: %s", tenant_id)
    conn = _identity_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "select tenant_id, slug, name from clinical_db.identity.tenants "
            "where tenant_id = %s limit 1",
            (tenant_id,),
        )
        rows = _rows_to_dicts(cur)
        return rows[0] if rows else None
    except Exception as e:
        log.exception("get_tenant_by_id failed for %s", tenant_id)
        raise RuntimeError(f"get_tenant_by_id failed: {e}") from e
    finally:
        conn.close()


def validate_invite_token(token: str) -> dict | None:
    """Return {token, tenant_id, role, expires_at, used_by_user_id} for
    a still-valid, unused token, or None.

    Used to display a tenant-label preview on /register before the form
    is submitted.
    """
    log.info("validate_invite_token: %s...", (token or "")[:6])
    conn = _identity_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            select token, tenant_id, role, expires_at, used_by_user_id
            from clinical_db.identity.invite_tokens
            where token = %s
            limit 1
            """,
            (token,),
        )
        rows = _rows_to_dicts(cur)
        if not rows:
            return None
        row = rows[0]
        if row.get("used_by_user_id"):
            return None
        if row.get("expires_at") is None:
            return None
        # Compare expiry to now (Snowflake TIMESTAMP_NTZ comes back as datetime)
        from datetime import datetime, timezone
        exp = row["expires_at"]
        if isinstance(exp, datetime):
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < datetime.now(timezone.utc):
                return None
        return row
    except Exception as e:
        log.exception("validate_invite_token failed")
        raise RuntimeError(f"validate_invite_token failed: {e}") from e
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import json
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python -m database.snowflake_reader <patient_id>")
        sys.exit(1)

    patient_id = sys.argv[1]
    entities = read_entities_for_patient(patient_id)
    documents = read_documents_for_patient(patient_id)

    print(json.dumps({
        "patient_id": patient_id,
        "entities_count": len(entities),
        "documents_count": len(documents),
        "first_entity": entities[0] if entities else None,
        "first_document": documents[0] if documents else None,
    }, indent=2, default=str))