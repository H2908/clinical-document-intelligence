"""In-memory job store for async background processing.

Phase 4 L2. Tracks status of long-running operations (document upload,
delete-with-regenerate) so the frontend can poll for completion.

In-memory by design - simplest correct option for local dev and the
demo. Jobs are lost on uvicorn restart; acceptable for the use case.
"""
from __future__ import annotations
import threading
import time
import uuid
from typing import Any, Optional


# Module-level store, guarded by a lock
_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


def create_job(kind: str, context: Optional[dict] = None) -> str:
    """Create a queued job, return its job_id."""
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    with _LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "kind": kind,
            "status": "queued",
            "created_at": time.time(),
            "started_at": None,
            "finished_at": None,
            "context": context or {},
            "result": None,
            "error": None,
        }
    return job_id


def mark_running(job_id: str) -> None:
    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id]["status"] = "running"
            _JOBS[job_id]["started_at"] = time.time()


def mark_completed(job_id: str, result: Any) -> None:
    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id]["status"] = "completed"
            _JOBS[job_id]["finished_at"] = time.time()
            _JOBS[job_id]["result"] = result


def mark_failed(job_id: str, error: str) -> None:
    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id]["status"] = "failed"
            _JOBS[job_id]["finished_at"] = time.time()
            _JOBS[job_id]["error"] = error


def get_job(job_id: str) -> Optional[dict]:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return None
        return dict(job)  # shallow copy so callers can't mutate the store


def list_jobs(limit: int = 50) -> list[dict]:
    with _LOCK:
        jobs = sorted(_JOBS.values(), key=lambda j: j["created_at"], reverse=True)
        return [dict(j) for j in jobs[:limit]]