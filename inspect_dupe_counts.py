"""Quick inspection of flag/contradiction duplication for pat_test_01.

Tells us:
  - Raw row counts (what overview card sees: 198/154)
  - Distinct counts by content (what dedup would yield)
  - Whether current rows are hashed (provenance_hash) or not
  - Whether we have status='open' filter at play

Read-only. No deletes here.
"""
import os
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()
PATIENT = "pat_test_01"

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

    print("=== CORE.flag ===")
    cur.execute(
        "SELECT COUNT(*), COUNT(provenance_hash), "
        "COUNT(DISTINCT category || '|' || description) "
        "FROM clinical_db.core.flag WHERE patient_id = %s",
        (PATIENT,),
    )
    total, hashed, distinct_by_content = cur.fetchone()
    print(f"  Raw rows:                  {total}")
    print(f"  With provenance_hash:      {hashed}")
    print(f"  Distinct (category,desc):  {distinct_by_content}")

    cur.execute(
        "SELECT COUNT(*) FROM clinical_db.core.flag "
        "WHERE patient_id = %s AND status = 'open'",
        (PATIENT,),
    )
    open_count = cur.fetchone()[0]
    print(f"  status='open' rows:        {open_count}")

    cur.execute(
        "SELECT COUNT(*) FROM clinical_db.core.flag "
        "WHERE patient_id = %s AND status IS NULL",
        (PATIENT,),
    )
    null_status = cur.fetchone()[0]
    print(f"  status IS NULL:            {null_status}")

    print()
    print("=== CORE.contradiction ===")
    cur.execute("DESC TABLE clinical_db.core.contradiction")
    cols = [r[0].lower() for r in cur.fetchall()]
    print(f"  Columns: {cols}")

    cur.execute(
        "SELECT COUNT(*) FROM clinical_db.core.contradiction WHERE patient_id = %s",
        (PATIENT,),
    )
    total_c = cur.fetchone()[0]
    print(f"  Raw rows:                  {total_c}")

    # Try common dedup keys
    cur.execute(
        "SELECT COUNT(DISTINCT category || '|' || COALESCE(doc_a_id,'') "
        "|| '|' || COALESCE(doc_b_id,'')) "
        "FROM clinical_db.core.contradiction WHERE patient_id = %s",
        (PATIENT,),
    )
    distinct_c = cur.fetchone()[0]
    print(f"  Distinct (cat,docA,docB):  {distinct_c}")

    print()
    print("=== Sample contradictions (3) ===")
    cur.execute(
        "SELECT category, doc_a_id, doc_b_id, created_at "
        "FROM clinical_db.core.contradiction "
        "WHERE patient_id = %s ORDER BY created_at DESC LIMIT 3",
        (PATIENT,),
    )
    for row in cur.fetchall():
        print(f"  {row}")
finally:
    conn.close()