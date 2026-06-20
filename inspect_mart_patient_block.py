"""Diagnostic: what does MART.patient_summary actually contain for
pat_fa9fb06f? Specifically the patient block of the summary VARIANT.

If the stored block has Margaret's real demographics -> endpoint or
frontend is overriding correctly stored data.

If the stored block has placeholder data (Test Patient / 1980-01-01) ->
briefing_agent wrote those placeholders. We trace upstream to find where.

If there's no patient block at all -> endpoint synthesises it from
somewhere we haven't found yet.
"""
import os
import json
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

PATIENT = "pat_fa9fb06f"

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
        "SELECT summary FROM clinical_db.mart.patient_summary WHERE patient_id = %s",
        (PATIENT,),
    )
    row = cur.fetchone()
    if not row:
        print(f"No MART.patient_summary row for {PATIENT}")
    else:
        raw = row[0]
        data = json.loads(raw) if isinstance(raw, str) else raw
        print("Top-level keys in stored summary:")
        if isinstance(data, dict):
            for k in data.keys():
                print(f"  {k}")
            print()
            print("Patient block (if any):")
            patient_block = data.get("patient")
            print(json.dumps(patient_block, indent=2, default=str))
        else:
            print(f"  (not a dict, type={type(data).__name__})")
finally:
    conn.close()


# Also check what's in CORE.patient for the same id
conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    password=os.environ["SNOWFLAKE_PASSWORD"],
    database="clinical_db",
    warehouse="clinical_wh",
    role=os.environ["SNOWFLAKE_ROLE"],
)
try:
    print()
    print("=" * 50)
    print(f"CORE.patient row for {PATIENT}:")
    cur = conn.cursor()
    cur.execute(
        "SELECT patient_id, name, dob, nhs_number, sex FROM clinical_db.core.patient WHERE patient_id = %s",
        (PATIENT,),
    )
    row = cur.fetchone()
    if row:
        print(f"  patient_id: {row[0]}")
        print(f"  name:       {row[1]}")
        print(f"  dob:        {row[2]}")
        print(f"  nhs_number: {row[3]}")
        print(f"  sex:        {row[4]}")
    else:
        print("  not found")
finally:
    conn.close()