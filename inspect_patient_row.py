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

print("=== core.patient row for pat_test_01 ===")
cur.execute("SELECT * FROM clinical_db.core.patient WHERE patient_id = 'pat_test_01'")
cols = [c[0] for c in cur.description]
row = cur.fetchone()
if row:
    for c, v in zip(cols, row):
        print(f"  {c:25s} {v}")
else:
    print("  NO ROW (patient block missing - this is the open partner ask)")

print("\n=== Document count ===")
cur.execute("SELECT COUNT(*) FROM clinical_db.core.document WHERE patient_id = 'pat_test_01'")
print(f"  {cur.fetchone()[0]} documents")

print("\n=== Conditions count ===")
cur.execute("SELECT COUNT(*) FROM clinical_db.core.condition WHERE patient_id = 'pat_test_01'")
print(f"  {cur.fetchone()[0]} condition rows")

print("\n=== Medications count ===")
cur.execute("SELECT COUNT(*) FROM clinical_db.core.medication WHERE patient_id = 'pat_test_01'")
print(f"  {cur.fetchone()[0]} medication rows")

print("\n=== Open flags count ===")
cur.execute("SELECT COUNT(*) FROM clinical_db.core.flag WHERE patient_id = 'pat_test_01' AND status = 'open'")
print(f"  {cur.fetchone()[0]} open flags")

print("\n=== Open contradictions count ===")
cur.execute("SELECT COUNT(*) FROM clinical_db.core.contradiction WHERE patient_id = 'pat_test_01' AND status = 'open'")
print(f"  {cur.fetchone()[0]} open contradictions")

conn.close()