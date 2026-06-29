"""
api/routes/auth.py — POST /auth/register, POST /auth/login,
GET /auth/me. JWT-in-localStorage auth for the Patient/Doctor UI.

Error envelope matches the rest of the API:
    {"error": {"code": "STR_CODE", "message": "human-readable"}}

Auth endpoints are intentionally NOT gated by X-API-Key (they ARE the
gateway to authentication — CONTRACT.md §3.11).
"""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.auth import (
    CurrentUser,
    get_current_user,
    hash_password,
    optional_user,
    sign_jwt,
    validate_password,
    verify_password,
)
from database import snowflake_reader, snowflake_writer

log = logging.getLogger("api.routes.auth")

router = APIRouter()


# ── Pydantic request / response shapes ───────────────────────────
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    token: str = Field(min_length=8, max_length=64)
    email: str = Field(min_length=3, max_length=254)
    # Pydantic only does a basic length floor; the real rules
    # (≥10 chars, ≥1 letter, ≥1 digit) are checked in api.auth.validate_password
    # so the route returns its own error code instead of 422.
    password: str = Field(min_length=8, max_length=256)
    display_name: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class AuthUser(BaseModel):
    user_id: str
    tenant_id: str
    email: str
    display_name: str
    role: str


class AuthResponse(BaseModel):
    token: str
    user: AuthUser


def _err(code: str, message: str, http_status: int) -> HTTPException:
    return HTTPException(
        status_code=http_status,
        detail={"error": {"code": code, "message": message}},
    )


# ── POST /auth/register ──────────────────────────────────────────
@router.post("/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest) -> AuthResponse:
    # 1. Validate email shape (Pydantic enforces min length but not format)
    if not _EMAIL_RE.match(body.email):
        raise _err("invalid_email", "Email format invalid.", 400)

    # 2. Validate password rules (server-side authoritative)
    pw_err = validate_password(body.password)
    if pw_err:
        raise _err("weak_password", pw_err, 400)

    # 3. Validate invite token before doing any writes (light probe)
    preview = snowflake_reader.validate_invite_token(body.token)
    if preview is None:
        raise _err("invalid_token", "Invite token is invalid, used, or expired.", 400)

    # 4. Atomic register via SP — handles the rest (token consume + email
    #    uniqueness) inside one transaction.
    try:
        pw_hash = hash_password(body.password)
        result = snowflake_writer.register_user(
            token=body.token,
            email=body.email,
            password_hash=pw_hash,
            display_name=body.display_name,
        )
    except Exception as e:
        log.exception("register_user SP failed")
        raise _err("registration_failed", "Could not register user.", 500)

    if "error" in result:
        err_code = result["error"]
        if err_code == "email_taken":
            raise _err("email_taken", "Email already registered.", 409)
        if err_code == "invalid_token":
            raise _err("invalid_token", "Invite token is invalid, used, or expired.", 400)
        raise _err(err_code, result.get("message", "Registration failed."), 400)

    user_id = result["user_id"]
    tenant_id = result["tenant_id"]
    role = result.get("role", "doctor")

    # 5. Sign JWT and return
    token = sign_jwt(user_id=user_id, tenant_id=tenant_id, role=role, email=body.email)
    return AuthResponse(
        token=token,
        user=AuthUser(
            user_id=user_id,
            tenant_id=tenant_id,
            email=body.email,
            display_name=body.display_name,
            role=role,
        ),
    )


# ── POST /auth/login ─────────────────────────────────────────────
@router.post("/auth/login", response_model=AuthResponse)
async def login(body: LoginRequest) -> AuthResponse:
    try:
        result = snowflake_writer.authenticate_user(body.email)
    except Exception as e:
        log.exception("authenticate_user SP failed")
        raise _err("login_failed", "Could not authenticate.", 500)

    # Constant-time-ish: still call verify_password with a dummy hash so
    # response time doesn't leak whether the email exists.
    if "error" in result and result["error"] == "not_found":
        verify_password(body.password, "$2b$12$" + "0" * 53)  # throwaway
        raise _err("invalid_credentials", "Email or password is incorrect.", 401)

    if "error" in result:
        raise _err("login_failed", result.get("message", "Login failed."), 500)

    if not verify_password(body.password, result["password_hash"]):
        raise _err("invalid_credentials", "Email or password is incorrect.", 401)

    # Touch last_login_at (best-effort, non-blocking)
    try:
        snowflake_writer.record_login(result["user_id"])
    except Exception:
        pass

    token = sign_jwt(
        user_id=result["user_id"],
        tenant_id=result["tenant_id"],
        role=result.get("role", "doctor"),
        email=result["email"],
    )
    return AuthResponse(
        token=token,
        user=AuthUser(
            user_id=result["user_id"],
            tenant_id=result["tenant_id"],
            email=result["email"],
            display_name=result["display_name"],
            role=result.get("role", "doctor"),
        ),
    )


# ── GET /auth/me ─────────────────────────────────────────────────
@router.get("/auth/me", response_model=AuthUser)
async def me(user: CurrentUser = Depends(get_current_user)) -> AuthUser:
    """Echo the current user from the JWT. The frontend uses this to
    refresh display_name after a server-side tenant rename."""
    # We could re-read from Snowflake for freshest display_name, but
    # the JWT already carries enough for the dashboard chrome.
    return AuthUser(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        email=user.email,
        display_name=user.email.split("@", 1)[0],  # placeholder; UI can re-fetch
        role=user.role,
    )


# ── GET /auth/invite-preview (helper for /register form) ────────
@router.get("/auth/invite-preview")
async def invite_preview(token: str, user: CurrentUser | None = Depends(optional_user)) -> dict:
    """Lightweight probe so the /register page can show which tenant
    a token binds the user to. Returns {valid: bool, tenant_slug?: str}.
    No auth required."""
    if not token or len(token) < 8:
        return {"valid": False}
    row = snowflake_reader.validate_invite_token(token)
    if row is None:
        return {"valid": False}
    tenant = snowflake_reader.get_tenant_by_id(row["tenant_id"])
    return {
        "valid": True,
        "tenant_id": row["tenant_id"],
        "tenant_slug": tenant["slug"] if tenant else None,
        "tenant_name": tenant["name"] if tenant else None,
        "role": row.get("role", "doctor"),
    }
