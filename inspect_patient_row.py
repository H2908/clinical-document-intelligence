"""Verify the just-inserted patient row is actually in Snowflake."""
import os
from dotenv import load_dotenv
load_dotenv()
import snowflake.connector

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
    SELECT patient_id, name, dob, nhs_number, sex, created_at
    FROM clinical_db.core.patient
    WHERE nhs_number = '999 999 0001'
""")
for row in cur.fetchall():
    print(row)
conn.close()