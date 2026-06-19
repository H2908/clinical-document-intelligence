"""Make list_patients query CORE.patient instead of returning MOCK_PATIENTS.

Bug: list_patients returns hardcoded MOCK list, so any patient added via
POST /patients (which writes to CORE.patient) never appears in the home
page list. Result: + Add patient appears to silently fail.

Fix: query CORE.patient with subquery counts for documents and open
flags. Return same response shape. Keep MOCK_PATIENTS as a fallback
when Snowflake unreachable (same pattern as getPatient).

Atomic anchored replacement.
"""
from pathlib import Path

p = Path("api/routes/patients.py")
src = p.read_text(encoding="utf-8")

old_func = '''def list_patients(search: Optional[str] = None) -> dict:
    items = MOCK_PATIENTS
    if search:
        s = search.lower()
        items = [p for p in items if s in p["name"].lower() or s in p["nhs_number"]]
    return {"patients": items}'''

new_func = '''def list_patients(search: Optional[str] = None) -> dict:
    """List patients from CORE.patient with document + open flag counts.

    Falls back to MOCK_PATIENTS only if Snowflake is unreachable, so the
    demo still works in offline development. Production path is the real
    query; MOCK_PATIENTS are now demo seed only.
    """
    import logging as _logging
    _log = _logging.getLogger(__name__)

    try:
        conn = _get_connection()
    except Exception as exc:
        _log.exception("list_patients: Snowflake connect failed, falling back to MOCK")
        items = MOCK_PATIENTS
        if search:
            s = search.lower()
            items = [p for p in items if s in p["name"].lower() or s in p["nhs_number"]]
        return {"patients": items}

    try:
        cur = conn.cursor()
        sql = """
            SELECT
                p.patient_id,
                p.name,
                p.dob,
                p.nhs_number,
                p.sex,
                p.last_updated,
                (SELECT COUNT(*) FROM clinical_db.core.document d
                 WHERE d.patient_id = p.patient_id) AS document_count,
                (SELECT COUNT(*) FROM clinical_db.core.flag f
                 WHERE f.patient_id = p.patient_id AND f.status = 'open')
                    AS open_flag_count
            FROM clinical_db.core.patient p
        """
        params: tuple = ()
        if search:
            sql += " WHERE LOWER(p.name) LIKE %s OR p.nhs_number LIKE %s"
            pat = f"%{search.lower()}%"
            params = (pat, pat)
        sql += " ORDER BY p.last_updated DESC NULLS LAST, p.patient_id"

        cur.execute(sql, params)
        rows = cur.fetchall()

        items = []
        for row in rows:
            pid, name, dob, nhs, sex, last_updated, doc_count, flag_count = row
            items.append({
                "id": pid,
                "name": name,
                "dob": str(dob) if dob else None,
                "nhs_number": nhs,
                "sex": sex,
                "document_count": doc_count or 0,
                "open_flag_count": flag_count or 0,
                "last_updated": str(last_updated) if last_updated else None,
            })
        return {"patients": items}
    finally:
        conn.close()'''

if "FROM clinical_db.core.patient p" in src and "_get_connection()" in src.split("def list_patients")[1].split("def ")[0]:
    print("[SKIP] list_patients already queries CORE.patient")
elif old_func not in src:
    print("[FAIL] list_patients anchor not found")
    raise SystemExit(1)
else:
    src = src.replace(old_func, new_func, 1)
    p.write_text(src, encoding="utf-8", newline="\n")
    print("[OK] list_patients now queries CORE.patient with counts; MOCK is fallback")