"""Add read_observations_for_patient() to database/snowflake_reader.py.

Mirrors read_entities_for_patient + read_documents_for_patient shape:
  - Opens a connection
  - SELECT from CORE.observation joined to CORE.document for context
  - Returns list of dicts via _rows_to_dicts helper
  - try/except/finally with logging

Atomic anchored insert after read_documents_for_patient.
"""
from pathlib import Path

p = Path("database/snowflake_reader.py")
src = p.read_text(encoding="utf-8")

if "def read_observations_for_patient" in src:
    print("[SKIP] read_observations_for_patient already present")
    raise SystemExit(0)

# Anchor: insert immediately before the "Quick test" comment header at module bottom
anchor = "# ---------------------------------------------------------------------------\n# Quick test\n# ---------------------------------------------------------------------------"

if anchor not in src:
    print("[FAIL] 'Quick test' section anchor not found")
    raise SystemExit(1)

new_function = '''def read_observations_for_patient(patient_id: str) -> list[dict[str, Any]]:
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
# Quick test
# ---------------------------------------------------------------------------'''

src = src.replace(anchor, new_function, 1)
p.write_text(src, encoding="utf-8", newline="\n")
print("OK read_observations_for_patient added")
print(f"File now {len(p.read_text(encoding='utf-8').splitlines())} lines")