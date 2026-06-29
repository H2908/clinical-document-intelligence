"""
api/auth.py — bcrypt helpers, JWT sign/verify, password rules, and
the `get_current_user` FastAPI dependency.

This module is loaded once on first request. It deliberately does not
require Snowflake at import time so the app boots even when Snowflake
is unavailable (mock-first rule, CONTRACT.md §7).

JWT format
----------
  Algorithm: HS256
  Claims:    {sub: <user_id>, tid: <tenant_id>, role: <role>,
              email: <email>, exp: <unix-ts>, iat: <unix-ts>}
  Lifetime:  12 hours (configurable via JWT_TTL_SECONDS env var)

ENV vars used
-------------
  JWT_SECRET         (required for production; missing in dev =>
                      a per-process ephemeral secret is generated, with
                      a warning logged on app startup)

The token is opaque to the client except for its visible JWT header
and payload. Decode-only on the server side.
"""
from __future__ import annotations

import logging
import os
import secrets
import time
from dataclasses import dataclass

import bcrypt
import jwt
from fastapi import Header, HTTPException, status

log = logging.getLogger("api.auth")


# ── JWT_SECRET ─────────────────────────────────────────────────────
# If a real secret is provided via env, use it. Otherwise, generate
# an ephemeral one at startup so dev mode still works — log a loud
# warning so nobody deploys this.
_JWT_SECRET = os.environ.get("JWT_SECRET")
if not _JWT_SECRET:
    _JWT_SECRET = secrets.token_urlsafe(48)
    log.warning(
        "JWT_SECRET is not set — generated an ephemeral secret for this "
        "process. All tokens will be invalid after uvicorn restart. Set "
        "JWT_SECRET in .env for production."
    )

JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = int(os.environ.get("JWT_TTL_SECONDS", str(12 * 3600)))


# ── Password rules ───────────────────────────────────────────────
# Mirrors the registration form's client-side validation. Centralised
# here so the server is never the source of a weaker rule than the UI.
def validate_password(pw: str) -> str | None:
    """Return an error message if the password is invalid, else None."""
    if not isinstance(pw, str):
        return "Password must be a string."
    if len(pw) < 10:
        return "Password must be at least 10 characters."
    if not any(c.isdigit() for c in pw):
        return "Password must contain at least one digit."
    if not any(c.isalpha() for c in pw):
        return "Password must contain at least one letter."
    return None


def hash_password(pw: str) -> str:
    """bcrypt with cost factor 12. Returns ASCII string."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pw.encode("utf-8"), salt).decode("ascii")


def verify_password(pw: str, hashed: str) -> bool:
    """Constant-time bcrypt compare."""
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("ascii"))
    except Exception:
        return False


# ── JWT helpers ──────────────────────────────────────────────────
def sign_jwt(*, user_id: str, tenant_id: str, role: str, email: str) -> str:
    """Return a signed JWT string for the given user."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "tid": tenant_id,
        "role": role,
        "email": email,
        "iat": now,
        "exp": now + JWT_TTL_SECONDS,
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt.PyJWTError on any failure."""
    return jwt.decode(token, _JWT_SECRET, algorithms=[JWT_ALGORITHM])


# ── Current-user dependency ──────────────────────────────────────
@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    tenant_id: str
    role: str
    email: str


async def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    """Read `Authorization: Bearer <jwt>`, decode, return CurrentUser.

    Raises 401 with CONTRACT error envelope on missing / bad / expired
    tokens.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Authorization header missing or malformed."}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(None, 1)[1].strip()
    try:
        payload = decode_jwt(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "TOKEN_EXPIRED", "message": "Token has expired."}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Token is invalid."}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentUser(
        user_id=str(payload["sub"]),
        tenant_id=str(payload["tid"]),
        role=str(payload.get("role", "doctor")),
        email=str(payload.get("email", "")),
    )


# ── Optional (no-op) auth dependency for development ─────────────
# When REQUIRE_AUTH=False, skip token enforcement. Routes still
# accept a token and decode it if present, but missing tokens are
# fine. Lets the app boot without an /auth/login flow during early
# integration.
REQUIRE_AUTH = os.environ.get("REQUIRE_AUTH", "false").lower() == "true"


async def optional_user(authorization: str | None = Header(default=None)) -> CurrentUser | None:
    """Best-effort decode. Returns None when missing/invalid."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(None, 1)[1].strip()
    try:
        payload = decode_jwt(token)
    except jwt.PyJWTError:
        return None
    return CurrentUser(
        user_id=str(payload["sub"]),
        tenant_id=str(payload["tid"]),
        role=str(payload.get("role", "doctor")),
        email=str(payload.get("email", "")),
    )
