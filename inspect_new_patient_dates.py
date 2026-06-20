"""Diagnostic: check CORE.document.document_date for the new patient.

If document_date in CORE matches the actual PDF date (e.g. 2024-01-12),
the bug is downstream (briefing agent or reader).

If document_date in CORE is today (2026-06-19), the bug is at ingestion -
the upload API didn't capture the user-provided date and defaulted to NOW.
"""
import os
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    password=os.environ["SNOWFLAKE_PASSWORD"],
    database="clinical_db",
    warehouse="clinical_wh",
    role=os.environ["SNOWFLAKE_ROLE"],
)
try:
    cur = conn.cursor()

    # Find the latest non-test-01 patient (likely the new Margaret Thompson)
    cur.execute("""
        SELECT patient_id, name, nhs_number
        FROM clinical_db.core.patient
        WHERE patient_id NOT IN ('pat_test_01')
        ORDER BY last_updated DESC NULLS LAST
        LIMIT 5
    """)
    print("Recent patients:")
    for row in cur.fetchall():
        print(f"  {row[0]:<25} {row[1]:<30} {row[2]}")

    # Show document_date for all non-test-01 documents
    cur.execute("""
        SELECT d.patient_id, d.document_id, d.doc_type, d.document_date, d.created_at
        FROM clinical_db.core.document d
        WHERE d.patient_id != 'pat_test_01'
        ORDER BY d.created_at DESC
        LIMIT 10
    """)
    print()
    print("Recent documents (non-pat_test_01):")
    print(f"  {'patient_id':<25} {'document_id':<22} {'doc_type':<18} {'document_date':<15} {'created_at'}")
    for row in cur.fetchall():
        print(f"  {row[0]:<25} {row[1]:<22} {row[2]:<18} {str(row[3]):<15} {row[4]}")
finally:
    conn.close()