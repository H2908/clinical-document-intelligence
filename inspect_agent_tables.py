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

for tbl in [
    "clinical_db.core.flag",
    "clinical_db.core.contradiction",
    "clinical_db.core.timeline_event",
    "clinical_db.mart.patient_summary",
]:
    print(f"\n=== {tbl} ===")
    try:
        cur.execute(f"DESCRIBE TABLE {tbl}")
        for r in cur.fetchall():
            print(f"  {r[0]:30s}  {r[1]}")
    except Exception as e:
        print(f"  ERROR: {e}")

print(f"\n=== Sample row counts for pat_test_01 ===")
for tbl in [
    "clinical_db.core.flag",
    "clinical_db.core.contradiction",
    "clinical_db.core.timeline_event",
    "clinical_db.mart.patient_summary",
]:
    cur.execute(f"SELECT COUNT(1) FROM {tbl} WHERE patient_id='pat_test_01'")
    n = cur.fetchone()[0]
    print(f"  {tbl}: {n} rows")

conn.close()