from dotenv import load_dotenv
load_dotenv()
import snowflake.connector, os
from collections import Counter

conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    password=os.environ["SNOWFLAKE_PASSWORD"],
    database="clinical_db",
    warehouse="clinical_wh",
    role=os.environ["SNOWFLAKE_ROLE"],
)
cur = conn.cursor()

print("=== Entity types in CORE.entity for pat_test_01 ===")
cur.execute("""
    SELECT entity_type, COUNT(*) AS n
    FROM clinical_db.core.entity
    WHERE patient_id = 'pat_test_01'
    GROUP BY entity_type
    ORDER BY n DESC
""")
for r in cur.fetchall():
    print(f"  {r[0]!r:30s}  {r[1]} rows")

print("\n=== Sample Diagnosis entities (first 8) ===")
cur.execute("""
    SELECT text, negated, icd10_code
    FROM clinical_db.core.entity
    WHERE patient_id = 'pat_test_01'
      AND LOWER(entity_type) = 'diagnosis'
    LIMIT 8
""")
rows = cur.fetchall()
if not rows:
    print("  (no rows where entity_type LOWERS to 'diagnosis')")
for r in rows:
    print(f"  text={r[0]!r}  negated={r[1]}  icd10={r[2]}")

print("\n=== Sample Drug entities (first 8) ===")
cur.execute("""
    SELECT text, negated, normalised_value
    FROM clinical_db.core.entity
    WHERE patient_id = 'pat_test_01'
      AND LOWER(entity_type) = 'drug'
    LIMIT 8
""")
rows = cur.fetchall()
if not rows:
    print("  (no rows where entity_type LOWERS to 'drug')")
for r in rows:
    print(f"  text={r[0]!r}  negated={r[1]}  normalised={r[2]}")

conn.close()