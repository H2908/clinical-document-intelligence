"""Verify Task 2 end-state: bnf_code on Drug entities + provenance_hash on flags."""
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

    print("=== Drug entities for pat_test_01 ===")
    cur.execute("""
        SELECT COUNT(*) AS total, COUNT(bnf_code) AS with_bnf,
               COUNT(*) - COUNT(bnf_code) AS without_bnf
        FROM clinical_db.core.entity
        WHERE patient_id = 'pat_test_01' AND entity_type = 'Drug'
    """)
    total, with_bnf, without_bnf = cur.fetchone()
    pct = (with_bnf / total * 100) if total else 0
    print(f"  Drug entities total:    {total}")
    print(f"  With bnf_code:          {with_bnf} ({pct:.0f}%)")
    print(f"  Without bnf_code:       {without_bnf}")

    print()
    print("=== Sample Drug entities (5) ===")
    cur.execute("""
        SELECT text, normalised_value, bnf_code
        FROM clinical_db.core.entity
        WHERE patient_id = 'pat_test_01' AND entity_type = 'Drug'
        LIMIT 5
    """)
    for row in cur.fetchall():
        text, norm, bnf = row
        bnf_str = bnf or "NULL"
        print(f"  text={text!r:<30} norm={norm!r:<15} bnf={bnf_str}")

    print()
    print("=== Flags for pat_test_01 ===")
    cur.execute("""
        SELECT COUNT(*) AS total, COUNT(provenance_hash) AS hashed,
               COUNT(*) - COUNT(provenance_hash) AS without_hash
        FROM clinical_db.core.flag
        WHERE patient_id = 'pat_test_01'
    """)
    total, hashed, without = cur.fetchone()
    pct = (hashed / total * 100) if total else 0
    print(f"  Flags total:            {total}")
    print(f"  With provenance_hash:   {hashed} ({pct:.0f}%)")
    print(f"  Without (NULL):         {without}")
finally:
    conn.close()