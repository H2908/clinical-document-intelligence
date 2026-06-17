"""Job status endpoint. GET /jobs/{job_id} for polling."""
from fastapi import APIRouter, HTTPException

from api.jobs import get_job, list_jobs

router = APIRouter()


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str) -> dict:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found",
                              "message": f"Job {job_id} not found"}},
        )
    return job


@router.get("/jobs")
def list_recent_jobs(limit: int = 50) -> dict:
    return {"jobs": list_jobs(limit=limit)}