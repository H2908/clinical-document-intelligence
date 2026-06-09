from dotenv import load_dotenv
load_dotenv()
import snowflake.connector, os

conn = snowflake.connector.connect(
    account   = os.environ["SNOWFLAKE_ACCOUNT"],
    user      = os.environ["SNOWFLAKE_USER"],
    password  = os.environ["SNOWFLAKE_PASSWORD"],
    database  = "clinical_db",
    warehouse = "clinical_wh",
    role      = os.environ["SNOWFLAKE_ROLE"],
)
cur = conn.cursor()

cur.execute("SELECT COUNT(1) FROM clinical_db.core.document WHERE patient_id = 'pat_test_01'")
print("CORE.document rows:", cur.fetchone()[0])

cur.execute("SELECT COUNT(1) FROM clinical_db.raw.raw_documents WHERE patient_id = 'pat_test_01'")
print("RAW.raw_documents rows:", cur.fetchone()[0])

conn.close()
