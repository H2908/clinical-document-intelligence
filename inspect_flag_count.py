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

print("=== Total rows in core.flag for pat_test_01 ===")
cur.execute("SELECT COUNT(*) FROM clinical_db.core.flag WHERE patient_id = 'pat_test_01'")
print(f"  {cur.fetchone()[0]} rows")

print("\n=== Distinct categories ===")
cur.execute("""
    SELECT category, COUNT(*) as n
    FROM clinical_db.core.flag
    WHERE patient_id = 'pat_test_01'
    GROUP BY category
    ORDER BY n DESC
""")
for r in cur.fetchall():
    print(f"  {r[0]:50s} {r[1]}")

print("\n=== Distinct (category, description) pairs ===")
cur.execute("""
    SELECT COUNT(DISTINCT category || '|' || description) FROM clinical_db.core.flag
    WHERE patient_id = 'pat_test_01'
""")
print(f"  {cur.fetchone()[0]} distinct (category, description) pairs")

conn.close()