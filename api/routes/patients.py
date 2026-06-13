"""
Patient list + detail endpoints.

GET /patients         - list view (Phase 1 mock kept for the demo's landing page)
POST /patients        - create (Phase 1 mock)
GET /patients/{id}    - detail view (REAL: reads CORE.patient + MART.patient_summary)
DELETE /patients/{id} - placeholder
"""
import os
from datetime import date, datetime
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import snowflake.connector

router = APIRouter()

# ---------- Phase 1 mock list (kept so the landing page still has data) ----------
MOCK_PATIENTS = [
    {
        "id": "pat_8f3a", "name": "Mohammed Al-Rashidi", "dob": "1970-03-12",
        "nhs_number": "485 621 3847", "sex": "M",
        "document_count": 3, "open_flag_count": 3,
        "last_updated": "2024-04-10T09:00:00Z",
    },
    {
        "id": "pat_2c7b", "name": "Eleanor Whitfield", "dob": "1948-09-28",
        "nhs_number": "602 114 7785", "sex": "F",
        "document_count": 3, "open_flag_count": 2,
        "last_updated": "2024-05-02T10:30:00Z",
    },
    {
        "id": "pat_4d1e", "name": "Daniel Osei", "dob": "1991-07-05",
        "nhs_number": "733 908 2210", "sex": "M",
        "document_count": 2, "open_flag_count": 1,
        "last_updated": "2024-02-22T14:15:00Z",
    },
]


class NewPatient(BaseModel):
    name: str
    dob: date
    nhs_number: str
    sex: Literal["M", "F", "Other"]


def _sf_conn():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        database="clinical_db",
        warehouse="clinical_wh",
        role=os.environ["SNOWFLAKE_ROLE"],
    )


def _age(dob_value) -> int:
    """Compute age from a date or string YYYY-MM-DD."""
    if dob_value is None:
        return 0
    if isinstance(dob_value, str):
        try:
            dob_value = date.fromisoformat(dob_value[:10])
        except Exception:
            return 0
    today = date.today()
    return today.year - dob_value.year - (
        (today.month, today.day) < (dob_value.month, dob_value.day)
    )


def _iso(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


# ---------------- LIST ----------------
@router.get("/patients")
def list_patients(search: Optional[str] = None) -> dict:
    items = MOCK_PATIENTS
    if search:
        s = search.lower()
        items = [p for p in items if s in p["name"].lower() or s in p["nhs_number"]]
    return {"patients": items}


# ---------------- CREATE (real Snowflake) ----------------
@router.post("/patients", status_code=status.HTTP_201_CREATED)
def create_patient(body: NewPatient) -> dict:
    """Insert a new patient into CORE.patient.

    Returns 409 Conflict if the NHS number already exists.
    Returns 503 if Snowflake is unreachable.
    """
    import uuid as _uuid
    import logging as _logging
    _log = _logging.getLogger(__name__)

    patient_id = f"pat_{_uuid.uuid4().hex[:8]}"
    now = datetime.utcnow().replace(microsecond=0)

    try:
        conn = _sf_conn()
    except Exception as e:
        _log.exception("Snowflake connect failed for create_patient")
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "database_unavailable",
                              "message": "Could not connect to data warehouse"}},
        )

    try:
        cur = conn.cursor()

        # Uniqueness check on NHS number (the human-facing key)
        cur.execute(
            "SELECT patient_id FROM clinical_db.core.patient WHERE nhs_number = %s",
            (body.nhs_number,),
        )
        existing = cur.fetchone()
        if existing:
            raise HTTPException(
                status_code=409,
                detail={"error": {"code": "patient_exists",
                                  "message": f"A patient with NHS number {body.nhs_number} already exists",
                                  "existing_patient_id": existing[0]}},
            )

        cur.execute(
            """
            INSERT INTO clinical_db.core.patient
                (patient_id, name, dob, nhs_number, sex, created_at, last_updated)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (patient_id, body.name, body.dob, body.nhs_number, body.sex, now, now),
        )
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        _log.exception("INSERT into CORE.patient failed for %s", body.nhs_number)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": f"Patient creation failed: {e}"}},
        )
    finally:
        conn.close()

    return {
        "id": patient_id,
        "name": body.name,
        "dob": body.dob.isoformat(),
        "nhs_number": body.nhs_number,
        "sex": body.sex,
        "document_count": 0,
        "open_flag_count": 0,
        "last_updated": now.isoformat() + "Z",
    }


# ---------------- DETAIL (real Snowflake) ----------------
@router.get("/patients/{patient_id}")
def get_patient(patient_id: str) -> dict:
    # 1. Try CORE.patient. Fall back to mock for the three demo IDs.
    conn = _sf_conn()
    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT patient_id, name, dob, nhs_number, sex, last_updated "
            "FROM clinical_db.core.patient WHERE patient_id = %s",
            (patient_id,),
        )
        row = cur.fetchone()

        if row is None:
            # Not in CORE.patient. Check mock fallback for the demo IDs.
            for p in MOCK_PATIENTS:
                if p["id"] == patient_id:
                    return _build_mock_overview(p)
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": "not_found",
                        "message": f"Patient {patient_id} does not exist.",
                    }
                },
            )

        _, name, dob, nhs_number, sex, last_updated = row

        # 2. Counts: documents, open flags, open contradictions
        cur.execute(
            "SELECT COUNT(*) FROM clinical_db.core.document WHERE patient_id = %s",
            (patient_id,),
        )
        document_count = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM clinical_db.core.flag "
            "WHERE patient_id = %s AND status = 'open'",
            (patient_id,),
        )
        open_flag_count = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM clinical_db.core.contradiction "
            "WHERE patient_id = %s AND status = 'open'",
            (patient_id,),
        )
        contradiction_count = cur.fetchone()[0]

        # 3. Conditions + medications: extract from MART.patient_summary.summary
        # (VARIANT column) - same source the briefing endpoint reads.
        cur.execute(
            "SELECT summary FROM clinical_db.mart.patient_summary "
            "WHERE patient_id = %s",
            (patient_id,),
        )
        mart_row = cur.fetchone()
        conditions: list = []
        medications: list = []
        if mart_row and mart_row[0] is not None:
            import json as _json
            raw = mart_row[0]
            summary_dict = _json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(summary_dict, dict):
                # Briefing agent writes active_conditions / current_medications;
                # frontend type expects conditions / medications.
                conditions = (
                    summary_dict.get("active_conditions")
                    or summary_dict.get("conditions")
                    or []
                )
                medications = (
                    summary_dict.get("current_medications")
                    or summary_dict.get("medications")
                    or []
                )

        # Normalise medication shape so frontend's `dose` / `started` / `flag`
        # columns render even when MART rows only carry drug + normalised.
        for m in medications:
            m.setdefault("dose", None)
            m.setdefault("started", None)
            m.setdefault("flag", None)

        # 4. Top 3 open flags ordered by severity (HIGH > MEDIUM > LOW) then created_at.
        cur.execute(
            """
            SELECT flag_id, severity, category, description,
                   source_document_id, status, created_at
            FROM clinical_db.core.flag
            WHERE patient_id = %s AND status = 'open'
            ORDER BY
                CASE severity
                  WHEN 'HIGH' THEN 0
                  WHEN 'MEDIUM' THEN 1
                  WHEN 'LOW' THEN 2
                  ELSE 3
                END,
                created_at DESC
            LIMIT 3
            """,
            (patient_id,),
        )
        top_flags = []
        for fid, sev, cat, desc, sdoc, st, cat_created in cur.fetchall():
            top_flags.append({
                "flag_id": fid,
                "severity": sev,
                "category": cat,
                "description": desc,
                "source_document_id": sdoc,
                "status": st,
                "created_at": _iso(cat_created),
            })

        return {
            "id": patient_id,
            "name": name,
            "dob": _iso(dob),
            "nhs_number": nhs_number,
            "sex": sex,
            "age": _age(dob),
            "document_count": document_count,
            "open_flag_count": open_flag_count,
            "last_updated": _iso(last_updated),
            "stats": {
                "document_count": document_count,
                "open_flag_count": open_flag_count,
                "contradiction_count": contradiction_count,
            },
            "conditions": conditions,
            "medications": medications,
            "top_flags": top_flags,
        }

    finally:
        try:
            conn.close()
        except Exception:
            pass


def _build_mock_overview(p: dict) -> dict:
    """Phase 1 mock overview kept for the three demo IDs."""
    return {
        **p,
        "age": 54,
        "stats": {
            "document_count": p["document_count"],
            "open_flag_count": p["open_flag_count"],
            "contradiction_count": 1,
        },
        "conditions": [
            {"name": "Dilated cardiomyopathy", "icd10_code": "I42.0"},
            {"name": "Type 2 diabetes mellitus", "icd10_code": "E11"},
        ],
        "medications": [
            {"drug": "Bisoprolol", "dose": "2.5 mg OD",
             "started": "2024-02-28", "flag": None},
            {"drug": "Metformin", "dose": "1 g BD",
             "started": "2019-04-10",
             "flag": "eGFR below recommended threshold"},
        ],
        "top_flags": [],
    }


@router.delete("/patients/{patient_id}")
def delete_patient(patient_id: str) -> dict:
    return {"deleted": True, "patient_id": patient_id}