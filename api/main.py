"""
Clinical Document Intelligence — FastAPI entry point.

Phase 1: routes return mock JSON in the shapes defined by docs/API_CONTRACT.md.
Phase 2 will replace the mocks with real Snowflake reads and S3 uploads.
"""
from dotenv import load_dotenv
load_dotenv()
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

from api.routes import (
    patients,
    documents,
    notes,
    labs,
    flags,
    contradictions,
    briefing,
    timeline,
    jobs,
)

# ----------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
)
log = logging.getLogger("api")


# ----------------------------------------------------------------------
# Lifespan — runs on startup and shutdown
# ----------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    log.info("API starting up (Phase 1 — mock data)")
    # Phase 2: open Snowflake connection pool here
    # Phase 2: verify S3 bucket is reachable here
    yield
    # Shutdown
    log.info("API shutting down")
    # Phase 2: close Snowflake connection pool here


# ----------------------------------------------------------------------
# App
# ----------------------------------------------------------------------
app = FastAPI(
    title="Clinical Document Intelligence",
    description=(
        "Doctor-facing API. Turns scattered patient documents into a "
        "structured, queryable record. See docs/API_CONTRACT.md."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ----------------------------------------------------------------------
# Middleware
# ----------------------------------------------------------------------
# CORS — open in dev, locked down in production via env var later
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Next.js dev server
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------------
# Error handlers — return the contract's error shape
# ----------------------------------------------------------------------
def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    log.warning("Validation error: %s", exc.errors())
    return JSONResponse(
        status_code=422,
        content=error_body("validation_error", "Request body failed validation."),
    )


@app.exception_handler(404)
async def not_found_handler(_: Request, __):
    return JSONResponse(
        status_code=404,
        content=error_body("not_found", "The requested resource does not exist."),
    )


@app.exception_handler(500)
async def server_error_handler(_: Request, exc):
    log.exception("Unhandled error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=error_body("internal_error", "An internal error occurred."),
    )

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    log.exception("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "An internal error occurred."}},
    )
# ----------------------------------------------------------------------
# Routers
# ----------------------------------------------------------------------
app.include_router(patients.router,        prefix="/api", tags=["patients"])
app.include_router(documents.router,       prefix="/api", tags=["documents"])
app.include_router(notes.router,           prefix="/api", tags=["notes"])
app.include_router(labs.router,            prefix="/api", tags=["labs"])
app.include_router(flags.router,           prefix="/api", tags=["flags"])
app.include_router(contradictions.router,  prefix="/api", tags=["contradictions"])
app.include_router(briefing.router,        prefix="/api", tags=["briefing"])
app.include_router(timeline.router, prefix="/api", tags=["timeline"])
app.include_router(jobs.router,     prefix="/api", tags=["jobs"])

# ----------------------------------------------------------------------
# Health
# ----------------------------------------------------------------------
@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness check. Used by docker-compose, monitoring, the frontend."""
    return {"status": "ok", "version": app.version}


@app.get("/", tags=["meta"])
def root() -> dict:
    """Friendly landing — point devs at the Swagger UI."""
    return {
        "name": app.title,
        "version": app.version,
        "docs": "/docs",
        "health": "/health",
    }