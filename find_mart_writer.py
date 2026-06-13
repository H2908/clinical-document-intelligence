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

print("=== All procedures in MART ===")
cur.execute("SHOW PROCEDURES IN SCHEMA clinical_db.mart")
for r in cur.fetchall():
    print(f"  {r[1]}")

print("\n=== All procedures in CORE ===")
cur.execute("SHOW PROCEDURES IN SCHEMA clinical_db.core")
for r in cur.fetchall():
    name = r[1]
    if name.startswith("SP_") or "SUMMARY" in name or "BRIEF" in name:
        print(f"  {name}")

print("\n=== Last 10 row updates to MART.patient_summary ===")
cur.execute("""
    SELECT patient_id, generated_at, is_stale
    FROM clinical_db.mart.patient_summary
    ORDER BY generated_at DESC
    LIMIT 10
""")
for r in cur.fetchall():
    print(f"  {r[0]}  generated_at={r[1]}  stale={r[2]}")

conn.close()