from dotenv import load_dotenv
load_dotenv()
import snowflake.connector, os, json

conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    password=os.environ["SNOWFLAKE_PASSWORD"],
    database="clinical_db",
    warehouse="clinical_wh",
    role=os.environ["SNOWFLAKE_ROLE"],
)
cur = conn.cursor()
cur.execute("""
    SELECT summary
    FROM clinical_db.mart.patient_summary
    WHERE patient_id = 'pat_test_01'
""")
row = cur.fetchone()
if row:
    s = row[0]
    if isinstance(s, str):
        s = json.loads(s)
    print("Keys in MART.summary:", list(s.keys()))
    print()
    print(json.dumps(s, indent=2)[:3000])
conn.close()