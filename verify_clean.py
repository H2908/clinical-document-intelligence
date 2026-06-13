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
    "clinical_db.core.observation",
    "clinical_db.core.entity",
    "clinical_db.core.document",
    "clinical_db.mart.patient_summary",
]:
    cur.execute(f"SELECT COUNT(1) FROM {tbl} WHERE patient_id = 'pat_test_01'")
    print(f"  {tbl}: {cur.fetchone()[0]} rows")
conn.close()
