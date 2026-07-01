"""
demo/api/main.py Ã¢â‚¬â€ Clinical Document Intelligence Platform
EMNLP 2026 System Demonstration

Lightweight FastAPI that serves the full frontend from pre-computed
fixture JSON files. Zero Snowflake, zero S3, zero external dependencies.

Endpoints match frontend/lib/api.ts exactly.
POST/DELETE endpoints return realistic demo responses without persisting.

Run:
    cd demo
    uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations
import json
import re
import os
import uuid
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="Clinical Document Intelligence Ã¢â‚¬â€ Demo API",
    description="EMNLP 2026 System Demonstration",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ã¢â€â‚¬Ã¢â€â‚¬ Fixture loading Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

FIXTURES_DIR = Path(os.environ.get("FIXTURES_DIR", str(Path(__file__).parent.parent / "fixtures")))

def _load(patient_id: str) -> dict:
    p = FIXTURES_DIR / f"{patient_id}.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Patient {patient_id} not found"}})
    return json.loads(p.read_text(encoding="utf-8"))

def _all_fixtures() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(FIXTURES_DIR.glob("*.json"))]


def _parse_dose(drug_text: str) -> str:
    """Extract dose from drug name text e.g. 'Ramipril 5 mg OD' -> '5 mg'."""
    m = re.search(r"\d+[\d.]*\s*(?:mg|mcg|g|ml|units?|iu)", drug_text, re.IGNORECASE)
    return m.group(0) if m else ""


def _is_noise_med(drug_text: str) -> bool:
    """Filter out NER artefacts like 'furosemide dose', 'insulin therapy'."""
    noise = {"dose", "therapy", "treatment", "use", "review", "clinic", "started"}
    tokens = drug_text.strip().lower().split()
    return bool(tokens and tokens[-1] in noise) or len(tokens) > 5

# Ã¢â€â‚¬Ã¢â€â‚¬ In-memory job store (demo only) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

_JOBS: dict[str, dict] = {}

def _make_job(kind: str, context: dict) -> dict:
    job_id = str(uuid.uuid4())
    now = time.time()
    job = {
        "job_id": job_id,
        "kind": kind,
        "status": "completed",
        "created_at": now,
        "started_at": now,
        "finished_at": now + 2.1,
        "context": context,
        "result": {"message": "Demo mode: pipeline pre-computed"},
        "error": None,
    }
    _JOBS[job_id] = job
    return job

# Ã¢â€â‚¬Ã¢â€â‚¬ GET /api/patients Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.get("/api/patients")
def list_patients(search: Optional[str] = Query(None)):
    fixtures = _all_fixtures()
    patients = []
    for f in fixtures:
        flags = f.get("flags", [])
        open_flags = [fl for fl in flags if fl.get("status") != "resolved"]
        card = {
            "id": f["patient_id"],
            "name": f["patient_name"],
            "dob": f["patient_dob"],
            "nhs_number": f["patient_nhs"],
            "sex": f["patient_sex"],
            "document_count": len(f.get("documents", [])),
            "open_flag_count": len(open_flags),
            "last_updated": f.get("generated_at", datetime.utcnow().isoformat()) + "Z",
        }
        if search:
            q = search.lower()
            if q not in card["name"].lower() and q not in card["nhs_number"].lower():
                continue
        patients.append(card)
    return {"patients": patients}

# Ã¢â€â‚¬Ã¢â€â‚¬ GET /api/patients/{id} Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.get("/api/patients/{patient_id}")
def get_patient(patient_id: str):
    f = _load(patient_id)
    flags = f.get("flags", [])
    open_flags = [fl for fl in flags if fl.get("status") != "resolved"]
    contradictions = f.get("contradictions", [])
    # Compute age from dob
    dob = f["patient_dob"]
    try:
        from datetime import date
        d = date.fromisoformat(dob)
        today = date.today()
        age = today.year - d.year - ((today.month, today.day) < (d.month, d.day))
    except Exception:
        age = 0
    # Top 3 flags
    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    top_flags = sorted(open_flags, key=lambda x: severity_order.get(x.get("severity", "LOW"), 2))[:3]
    return {
        "id": patient_id,
        "name": f["patient_name"],
        "dob": f["patient_dob"],
        "nhs_number": f["patient_nhs"],
        "sex": f["patient_sex"],
        "document_count": len(f.get("documents", [])),
        "open_flag_count": len(open_flags),
        "last_updated": f.get("generated_at", datetime.utcnow().isoformat()) + "Z",
        "age": age,
        "stats": {
            "document_count": len(f.get("documents", [])),
            "open_flag_count": len(open_flags),
            "contradiction_count": len(contradictions),
        },
        "conditions": f.get("conditions", [])[:10],
        "medications": [
            {
                "drug": m.get("drug", ""),
                "dose": m.get("dose", ""),
                "last_prescribed": m.get("document_date", ""),
                "started": m.get("started"),
                "flag": m.get("flag_text"),
                "normalised": m.get("normalised_value", ""),
            }
            for m in f.get("medications_deduped", f.get("medications", []))
        ],
        "top_flags": [
            {
                "flag_id": fl.get("flag_id", str(uuid.uuid4())),
                "severity": fl.get("severity", "MEDIUM"),
                "category": fl.get("category", ""),
                "description": fl.get("description", ""),
                "source_document_id": fl.get("source_document_id", ""),
                "status": fl.get("status", "open"),
                "created_at": fl.get("created_at", datetime.utcnow().isoformat() + "Z"),
            }
            for fl in top_flags
        ],
    }

# Ã¢â€â‚¬Ã¢â€â‚¬ GET /api/patients/{id}/briefing Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.get("/api/patients/{patient_id}/briefing")
def get_briefing(patient_id: str):
    f = _load(patient_id)
    flags = f.get("flags", [])
    open_flags = [fl for fl in flags if fl.get("status") != "resolved"]
    return {
        "patient_id": patient_id,
        "available": True,
        "generated_at": f.get("generated_at", datetime.utcnow().isoformat()) + "Z",
        "is_stale": False,
        "disclaimer": "Demo mode: pre-computed results from synthetic patient data.",
        "summary": {
            "patient": {
                "id": patient_id,
                "name": f["patient_name"],
                "dob": f["patient_dob"],
                "nhs_number": f["patient_nhs"],
                "sex": f["patient_sex"],
            },
            "conditions": f.get("conditions", [])[:8],
            "medications": [
                {
                    "drug": m.get("drug", ""),
                    "dose": m.get("dose", ""),
                    "last_prescribed": m.get("document_date", ""),
                    "started": m.get("started"),
                    "flag": m.get("flag_text"),
                    "normalised": m.get("normalised_value", ""),
                }
                for m in f.get("medications_deduped", f.get("medications", []))
            ],
            "open_flags": [
                {
                    "severity": fl.get("severity", "MEDIUM"),
                    "category": fl.get("category", ""),
                    "description": fl.get("description", ""),
                    "source_document_id": fl.get("source_document_id", ""),
                }
                for fl in open_flags
            ],
        },
    }

# Ã¢â€â‚¬Ã¢â€â‚¬ GET /api/patients/{id}/flags Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.get("/api/patients/{patient_id}/flags")
def get_flags(patient_id: str, status: Optional[str] = Query(None)):
    f = _load(patient_id)
    flags = f.get("flags", [])
    open_flags = [fl for fl in flags if fl.get("status", "open") != "resolved"]
    resolved_flags = [fl for fl in flags if fl.get("status", "open") == "resolved"]
    if status == "open":
        filtered = open_flags
    elif status == "resolved":
        filtered = resolved_flags
    else:
        filtered = flags
    return {
        "patient_id": patient_id,
        "open_count": len(open_flags),
        "resolved_count": len(resolved_flags),
        "flags": [
            {
                "flag_id": fl.get("flag_id", str(uuid.uuid4())),
                "severity": fl.get("severity", "MEDIUM"),
                "category": fl.get("category", ""),
                "description": fl.get("description", ""),
                "clinical_subject": fl.get("clinical_subject", ""),
                "source_document_id": fl.get("source_document_id", ""),
                "status": fl.get("status", "open"),
                "created_at": fl.get("created_at", datetime.utcnow().isoformat() + "Z"),
                "resolved_at": fl.get("resolved_at"),
            }
            for fl in filtered
        ],
    }

# Ã¢â€â‚¬Ã¢â€â‚¬ GET /api/patients/{id}/contradictions Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.get("/api/patients/{patient_id}/contradictions")
def get_contradictions(patient_id: str):
    f = _load(patient_id)
    contradictions = f.get("contradictions", [])
    return {
        "patient_id": patient_id,
        "count": len(contradictions),
        "contradictions": [
            {
                "contradiction_id": c.get("contradiction_id", str(uuid.uuid4())),
                "severity": c.get("severity", "HIGH"),
                "category": c.get("category", ""),
                "doc_a_id": c.get("doc_a_id", ""),
                "doc_a_statement": c.get("doc_a_statement", c.get("claim_a", "")),
                "doc_b_id": c.get("doc_b_id", ""),
                "doc_b_statement": c.get("doc_b_statement", c.get("claim_b", "")),
                "explanation": c.get("explanation", ""),
                "status": c.get("status", "open"),
                "created_at": c.get("created_at", datetime.utcnow().isoformat() + "Z"),
            }
            for c in contradictions
        ],
    }

# Ã¢â€â‚¬Ã¢â€â‚¬ GET /api/patients/{id}/timeline Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.get("/api/patients/{patient_id}/timeline")
def get_timeline(patient_id: str, event_type: Optional[str] = Query(None), limit: int = Query(200)):
    f = _load(patient_id)
    events = []

    # Document events
    for doc in f.get("documents", []):
        events.append({
            "event_id": str(uuid.uuid4()),
            "event_date": doc.get("document_date"),
            "event_type": "Document",
            "title": doc.get("file_name", "Document"),
            "icd10_code": None,
            "source_document_id": doc.get("document_id", ""),
            "created_at": datetime.utcnow().isoformat() + "Z",
        })

    # Condition/Diagnosis events - one per condition per document (with date)
    for c in f.get("conditions", []):
        name = c.get("name", "").strip()
        if name:
            events.append({
                "event_id": str(uuid.uuid4()),
                "event_date": c.get("document_date"),
                "event_type": "Diagnosis",
                "title": name,
                "icd10_code": c.get("icd10_code"),
                "source_document_id": c.get("document_id", ""),
                "created_at": datetime.utcnow().isoformat() + "Z",
            })

    # Medication events - one per unique drug
    for m in f.get("medications", []):
        drug = m.get("drug", "").strip()
        if drug:
            events.append({
                "event_id": str(uuid.uuid4()),
                "event_date": m.get("document_date"),
                "event_type": "Medication",
                "title": drug,
                "icd10_code": None,
                "source_document_id": m.get("document_id", ""),
                "created_at": datetime.utcnow().isoformat() + "Z",
            })

    # Conflict events - from entities
    for e in f.get("entities", []):
        if e.get("entity_type") == "Conflict" and not e.get("negated"):
            text = (e.get("text") or "").strip()
            if text and len(text) > 4:
                events.append({
                    "event_id": str(uuid.uuid4()),
                    "event_date": e.get("document_date"),
                    "event_type": "Conflict",
                    "title": text,
                    "icd10_code": None,
                    "source_document_id": e.get("document_id", ""),
                    "created_at": datetime.utcnow().isoformat() + "Z",
                })

    if event_type and event_type != "all":
        events = [e for e in events if e["event_type"] == event_type]
    events = events[:limit]
    return {"patient_id": patient_id, "count": len(events), "events": events}

# Ã¢â€â‚¬Ã¢â€â‚¬ GET /api/patients/{id}/labs Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.get("/api/patients/{patient_id}/labs")
def get_observations(patient_id: str):
    f = _load(patient_id)
    obs = f.get("observations", [])
    return {
        "patient_id": patient_id,
        "count": len(obs),
        "observations": [
            {
                "observation_id": str(uuid.uuid4()),
                "test": o.get("test", ""),
                "value": str(o.get("value", "")),
                "unit": o.get("unit") or "",
                "observation_date": o.get("observation_date") or o.get("document_date", ""),
                "source_document_id": o.get("source_document_id") or o.get("document_id", ""),
                "created_at": datetime.utcnow().isoformat() + "Z",
            }
            for o in obs
        ],
    }

# Ã¢â€â‚¬Ã¢â€â‚¬ GET /api/patients/{id}/notes Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.get("/api/patients/{patient_id}/notes")
def get_notes(patient_id: str):
    f = _load(patient_id)
    notes = [
        {
            "document_id": doc.get("document_id", ""),
            "doc_type": doc.get("doc_type", "clinic_letter"),
            "document_date": doc.get("document_date", ""),
            "source": "synthetic",
            "status": "processed",
            "extracted_text": doc.get("extracted_text", "")[:500],
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        for doc in f.get("documents", [])
    ]
    return {"patient_id": patient_id, "count": len(notes), "notes": notes}

# Ã¢â€â‚¬Ã¢â€â‚¬ GET /api/patients/{id}/documents Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.get("/api/patients/{patient_id}/documents")
def list_documents(patient_id: str):
    f = _load(patient_id)
    docs = [
        {
            "id": doc.get("document_id", ""),
            "name": doc.get("file_name", ""),
            "type": doc.get("doc_type", "clinic_letter"),
            "source": "synthetic",
            "date": doc.get("document_date", ""),
            "status": "processed",
        }
        for doc in f.get("documents", [])
    ]
    return {"documents": docs}

# Ã¢â€â‚¬Ã¢â€â‚¬ POST /api/patients/{id}/documents (demo: simulate pipeline) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.post("/api/patients/{patient_id}/documents")
async def upload_document(patient_id: str):
    job = _make_job("document_processing", {"patient_id": patient_id})
    return {
        "document_id": str(uuid.uuid4()),
        "job_id": job["job_id"],
        "status": "queued",
        "message": "Demo mode: document pipeline pre-computed. Results available immediately.",
    }

# Ã¢â€â‚¬Ã¢â€â‚¬ POST /api/patients/{id}/labs Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.post("/api/patients/{patient_id}/labs")
async def upload_lab(patient_id: str):
    job = _make_job("lab_processing", {"patient_id": patient_id})
    return {
        "document_id": str(uuid.uuid4()),
        "job_id": job["job_id"],
        "status": "queued",
        "doc_type": "lab_report",
        "message": "Demo mode: lab pipeline pre-computed.",
    }

# Ã¢â€â‚¬Ã¢â€â‚¬ POST /api/patients/{id}/notes Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.post("/api/patients/{patient_id}/notes")
async def post_note(patient_id: str):
    job = _make_job("note_processing", {"patient_id": patient_id})
    return {
        "document_id": str(uuid.uuid4()),
        "job_id": job["job_id"],
        "status": "queued",
        "entity_count": 0,
        "message": "Demo mode: note processed.",
    }

# Ã¢â€â‚¬Ã¢â€â‚¬ POST /api/patients Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.post("/api/patients")
async def create_patient():
    raise HTTPException(
        status_code=403,
        detail={"error": {"code": "demo_mode", "message": "Patient creation disabled in demo mode."}}
    )

# Ã¢â€â‚¬Ã¢â€â‚¬ DELETE /api/patients/{id} Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.delete("/api/patients/{patient_id}")
async def delete_patient(patient_id: str):
    raise HTTPException(
        status_code=403,
        detail={"error": {"code": "demo_mode", "message": "Patient deletion disabled in demo mode."}}
    )

# Ã¢â€â‚¬Ã¢â€â‚¬ GET /api/jobs/{job_id} Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = _JOBS.get(job_id)
    if not job:
        # Return a completed job for any unknown job_id (demo tolerance)
        return {
            "job_id": job_id,
            "kind": "unknown",
            "status": "completed",
            "created_at": time.time(),
            "started_at": time.time(),
            "finished_at": time.time(),
            "context": {},
            "result": {"message": "Demo mode"},
            "error": None,
        }
    return job

# Ã¢â€â‚¬Ã¢â€â‚¬ Health check Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.get("/api/health")
def health():
    fixtures = list(FIXTURES_DIR.glob("*.json"))
    return {
        "status": "ok",
        "mode": "demo",
        "patients_loaded": len(fixtures),
        "patient_ids": [p.stem for p in fixtures],
    }
