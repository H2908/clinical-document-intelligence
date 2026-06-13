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

try:
    cur.execute("DELETE FROM clinical_db.mart.patient_summary WHERE patient_id = 'pat_test_01'")
    print(f"Deleted {cur.rowcount} rows from MART.patient_summary")
    conn.commit()
except Exception as e:
    print(f"DELETE failed: {e}")
    print("Not a blocker — refresh_summary will overwrite on next upload.")

conn.close()