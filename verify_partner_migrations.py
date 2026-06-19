"""Confirm partner-side migrations landed as expected.

Two checks:
  1. CORE.flag has provenance_hash column (VARCHAR, NULL allowed)
  2. CORE.entity has bnf_code column (VARCHAR, NULL allowed)

If either fails, we stop and ask the partner rather than coding against
a phantom column.
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

    print("=== CORE.flag columns ===")
    cur.execute("DESC TABLE clinical_db.core.flag")
    flag_cols = cur.fetchall()
    has_provenance_hash = False
    for col in flag_cols:
        name, col_type = col[0], col[1]
        marker = "  <-- NEW" if name.lower() == "provenance_hash" else ""
        print(f"  {name:<25} {col_type}{marker}")
        if name.lower() == "provenance_hash":
            has_provenance_hash = True

    print()
    print("=== CORE.entity columns ===")
    cur.execute("DESC TABLE clinical_db.core.entity")
    entity_cols = cur.fetchall()
    has_bnf_code = False
    for col in entity_cols:
        name, col_type = col[0], col[1]
        marker = "  <-- NEW" if name.lower() == "bnf_code" else ""
        print(f"  {name:<25} {col_type}{marker}")
        if name.lower() == "bnf_code":
            has_bnf_code = True

    print()
    print("=== Summary ===")
    print(f"CORE.flag.provenance_hash: {'YES' if has_provenance_hash else 'MISSING'}")
    print(f"CORE.entity.bnf_code:      {'YES' if has_bnf_code else 'MISSING'}")

    if not (has_provenance_hash and has_bnf_code):
        print()
        print("[STOP] At least one column missing. Confirm with partner before continuing.")
        raise SystemExit(1)
    print()
    print("[OK] Both migrations landed. Safe to wire integration on our side.")
finally:
    conn.close()