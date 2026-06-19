"""Inspect what's actually in the data for medications.

Two outputs:
  1. Raw Drug entities for pat_test_01 - shows what NER captured and
     persisted including the original text (which probably has the
     dose) vs normalised_value (which probably doesn't).
  2. What the briefing endpoint returns - shows how the shaper presents
     medications to the frontend.

Tells us whether the dose is lost at NER time (data problem) or just
not surfaced by the shaper (presentation problem).
"""
import os
import json
import urllib.request
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

PATIENT = "pat_test_01"

# ============================================================================
# 1. Raw Drug entities from Snowflake
# ============================================================================
print("=" * 60)
print("1. Drug entities in CORE.entity")
print("=" * 60)
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
    cur.execute("""
        SELECT text, normalised_value, bnf_code, document_id
        FROM clinical_db.core.entity
        WHERE patient_id = %s AND entity_type = 'Drug'
        ORDER BY document_id, start_offset
    """, (PATIENT,))
    rows = cur.fetchall()
    print(f"{len(rows)} Drug entities total")
    print()
    print(f"{'text':<35} {'normalised_value':<20} {'bnf_code':<12} {'document_id'}")
    print("-" * 90)
    for text, norm, bnf, doc in rows:
        text_s = (text or "")[:34]
        norm_s = (norm or "")[:19]
        bnf_s = (bnf or "")[:11]
        print(f"{text_s:<35} {norm_s:<20} {bnf_s:<12} {doc}")
finally:
    conn.close()

# ============================================================================
# 2. What /briefing returns
# ============================================================================
print()
print("=" * 60)
print("2. /briefing endpoint medications payload")
print("=" * 60)
try:
    with urllib.request.urlopen(f"http://localhost:8000/api/patients/{PATIENT}/briefing") as r:
        data = json.loads(r.read())

    if not data.get("available"):
        print("[INFO] briefing.available is False - empty briefing")
    else:
        summary = data.get("summary", {})
        meds = summary.get("medications", []) or summary.get("current_medications", [])
        print(f"medications count: {len(meds)}")
        for m in meds:
            print(f"  {json.dumps(m, default=str)}")
except Exception as e:
    print(f"[FAIL] /briefing fetch: {e}")
    print("(Is uvicorn running on port 8000?)")

# ============================================================================
# 3. What /patients/{id} (overview) returns for medications
# ============================================================================
print()
print("=" * 60)
print("3. /patients/{id} overview endpoint medications payload")
print("=" * 60)
try:
    with urllib.request.urlopen(f"http://localhost:8000/api/patients/{PATIENT}") as r:
        data = json.loads(r.read())
    meds = data.get("medications", [])
    print(f"medications count: {len(meds)}")
    for m in meds:
        print(f"  {json.dumps(m, default=str)}")
except Exception as e:
    print(f"[FAIL] /patients/{PATIENT} fetch: {e}")