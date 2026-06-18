"""Check if mart.fhir_patient_bundle exists in Snowflake.

Tells us whether partner has executed 05_fhir.sql. Result determines
whether today's write-path block can be smoke-tested end-to-end.
"""
import os
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    password=os.environ["SNOWFLAKE_PASSWORD"],
    database="clinical_db",
    warehouse="clinical_wh",
    role=os.environ["SNOWFLAKE_ROLE"],
)
try:
    cur = conn.cursor()
    cur.execute("SHOW TABLES LIKE 'fhir_patient_bundle' IN SCHEMA clinical_db.mart")
    rows = cur.fetchall()
    print(f"Tables matching 'fhir_patient_bundle' in mart: {len(rows)}")
    if rows:
        print("FOUND - partner has executed 05_fhir.sql")
        # Show row count
        cur.execute("SELECT COUNT(*) FROM clinical_db.mart.fhir_patient_bundle")
        count = cur.fetchone()[0]
        print(f"  current row count: {count}")
    else:
        print("NOT FOUND - partner has not executed 05_fhir.sql yet")
finally:
    conn.close()