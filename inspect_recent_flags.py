from dotenv import load_dotenv
load_dotenv()
import snowflake.connector, os

conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    password=os.environ["SNOWFLAKE_PASSWORD"],
    database="clinical_db",
    warehouse="clinical_wh",
    role=os.environ["SNOWFLAKE_ROLE"],
)
cur = conn.cursor()

print("=== Count of rows in core.flag for pat_test_01 ===")
cur.execute("SELECT COUNT(*) FROM clinical_db.core.flag WHERE patient_id = 'pat_test_01'")
print(f"  {cur.fetchone()[0]} total rows")

print("\n=== Categories breakdown ===")
cur.execute("""
    SELECT category, severity, COUNT(*) FROM clinical_db.core.flag
    WHERE patient_id = 'pat_test_01'
    GROUP BY category, severity
    ORDER BY category
""")
for r in cur.fetchall():
    print(f"  {r[0]:50s} {r[1]:8s} {r[2]}")

print("\n=== All distinct flags (full row) ===")
cur.execute("""
    SELECT flag_id, severity, category, description, source_document_id, status, created_at
    FROM clinical_db.core.flag
    WHERE patient_id = 'pat_test_01'
    ORDER BY created_at DESC
""")
for r in cur.fetchall():
    print(f"  {r[1]:8s} {r[2]:40s} doc={r[4]}")
    print(f"           {r[3][:100]}")

conn.close()