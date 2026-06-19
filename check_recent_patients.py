"""List the 10 most recent patients in CORE.patient by created_at.

If a patient we just tried to add is here, the API write worked and the
problem is frontend-only (re-fetch, caching, routing).

If not here, the API write failed silently or never got called.
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
    cur.execute(
        "SELECT patient_id, name, nhs_number, created_at "
        "FROM clinical_db.core.patient "
        "ORDER BY created_at DESC LIMIT 10"
    )
    rows = cur.fetchall()
    print(f"{len(rows)} most recent patients:")
    for row in rows:
        print(f"  {row[0]:<25} {row[1]:<30} {row[2]:<15} {row[3]}")
finally:
    conn.close()