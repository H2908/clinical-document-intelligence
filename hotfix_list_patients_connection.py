"""Hotfix: replace _get_connection() in list_patients with the inline
snowflake.connector.connect pattern used elsewhere in patients.py.

api/routes/patients.py does not import _get_connection from the writer
module. It builds connections inline with snowflake.connector.connect.
The previous patch wrongly assumed _get_connection was available.

Anchored replacement of the connect() call inside list_patients.
"""
from pathlib import Path

p = Path("api/routes/patients.py")
src = p.read_text(encoding="utf-8")

if "snowflake.connector.connect" in src.split("def list_patients")[1].split("def ")[0]:
    print("[SKIP] list_patients already uses inline connect")
    raise SystemExit(0)

old = '''    try:
        conn = _get_connection()
    except Exception as exc:
        _log.exception("list_patients: Snowflake connect failed, falling back to MOCK")'''

new = '''    try:
        conn = snowflake.connector.connect(
            account=os.environ["SNOWFLAKE_ACCOUNT"],
            user=os.environ["SNOWFLAKE_USER"],
            password=os.environ["SNOWFLAKE_PASSWORD"],
            database="clinical_db",
            warehouse="clinical_wh",
            role=os.environ["SNOWFLAKE_ROLE"],
        )
    except Exception as exc:
        _log.exception("list_patients: Snowflake connect failed, falling back to MOCK")'''

if old not in src:
    print("[FAIL] _get_connection anchor not found")
    raise SystemExit(1)

src = src.replace(old, new, 1)
p.write_text(src, encoding="utf-8", newline="\n")
print("[OK] list_patients now uses inline snowflake.connector.connect")