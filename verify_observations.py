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

print("=== Observations for pat_test_01 ===")
cur.execute("""
    SELECT test, value, unit, observation_date, source_document_id
    FROM clinical_db.core.observation
    WHERE patient_id = 'pat_test_01'
    ORDER BY created_at DESC
    LIMIT 30
""")
rows = cur.fetchall()
print(f"Total rows returned: {len(rows)}")
for r in rows:
    print(f"  {r[0]:25s} {r[1]:10s} {r[2] or '':25s} {r[3]} {r[4]}")

conn.close()
