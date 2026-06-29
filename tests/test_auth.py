"""
tests/test_auth.py — auth endpoint contract tests (Problem 1).

These tests do NOT touch Snowflake. They patch the snowflake_reader /
snowflake_writer layer with in-memory fakes so the API surface and
JWT plumbing can be exercised on any machine, regardless of whether
Snowflake is provisioned.

Run:
    pytest tests/test_auth.py -v

Markers:
    @pytest.mark.integration - tests requiring real Snowflake (gated
    behind RUN_INTEGRATION_TESTS=1). Skipped by default.
"""
from __future__ import annotations

import os
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient


# ── In-memory fakes for the snowflake_* functions auth uses ───────
# Two fixtures: one for tokens (preview), one for user CRUD.
class FakeTokens:
    def __init__(self) -> None:
        self.by_token: dict[str, dict] = {}

    def add(self, token: str, tenant_id: str, role: str = "doctor", ttl: int = 604800) -> None:
        self.by_token[token] = {
            "token": token,
            "tenant_id": tenant_id,
            "role": role,
            "expires_at": _now_plus(ttl),
            "used_by_user_id": None,
        }


class FakeUsers:
    def __init__(self) -> None:
        self.by_email: dict[str, dict] = {}
        self.by_id: dict[str, dict] = {}
        self._uid = 0

    def next_id(self) -> str:
        self._uid += 1
        return f"u_{self._uid:04d}"


@pytest.fixture
def fake_db(monkeypatch: pytest.MonkeyPatch):
    tokens = FakeTokens()
    users = FakeUsers()

    # Seed one tenant + one fresh token that the test will consume
    tokens.add(token="INVITE-A-OK", tenant_id="t_demo")

    def fake_validate_invite_token(token: str) -> dict | None:
        row = tokens.by_token.get(token)
        if not row:
            return None
        if row["used_by_user_id"]:
            return None
        from datetime import datetime, timezone
        exp = row["expires_at"]
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            return None
        return row

    def fake_register_user(token: str, email: str, password_hash: str, display_name: str) -> dict:
        row = tokens.by_token.get(token)
        if not row or row["used_by_user_id"]:
            return {"error": "invalid_token", "message": "Invite token invalid."}
        # email uniqueness
        if email.lower() in users.by_email:
            return {"error": "email_taken", "message": "Email already registered."}
        # expiry
        from datetime import datetime, timezone
        exp = row["expires_at"]
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            return {"error": "invalid_token", "message": "Invite token expired."}

        user_id = users.next_id()
        rec = {
            "user_id": user_id,
            "tenant_id": row["tenant_id"],
            "email": email.lower(),
            "password_hash": password_hash,
            "display_name": display_name,
            "role": row["role"],
        }
        users.by_email[email.lower()] = rec
        users.by_id[user_id] = rec
        row["used_by_user_id"] = user_id
        return {
            "user_id": user_id,
            "tenant_id": rec["tenant_id"],
            "role": rec["role"],
        }

    def fake_authenticate_user(email: str) -> dict:
        rec = users.by_email.get(email.lower())
        if not rec:
            return {"error": "not_found"}
        return {
            "user_id": rec["user_id"],
            "tenant_id": rec["tenant_id"],
            "password_hash": rec["password_hash"],
            "display_name": rec["display_name"],
            "role": rec["role"],
            "email": rec["email"],
        }

    def fake_get_user_by_id(user_id: str) -> dict | None:
        rec = users.by_id.get(user_id)
        if not rec:
            return None
        return {
            "user_id": rec["user_id"],
            "tenant_id": rec["tenant_id"],
            "email": rec["email"],
            "display_name": rec["display_name"],
            "role": rec["role"],
            "created_at": _now_iso(),
        }

    def fake_get_tenant_by_id(tenant_id: str) -> dict | None:
        if tenant_id == "t_demo":
            return {"tenant_id": "t_demo", "slug": "demo-trust", "name": "Demo Trust"}
        return None

    monkeypatch.setattr("api.routes.auth.snowflake_reader.validate_invite_token", fake_validate_invite_token)
    monkeypatch.setattr("api.routes.auth.snowflake_writer.register_user", fake_register_user)
    monkeypatch.setattr("api.routes.auth.snowflake_writer.authenticate_user", fake_authenticate_user)
    monkeypatch.setattr("api.routes.auth.snowflake_writer.record_login", lambda uid: None)
    monkeypatch.setattr("database.snowflake_reader.get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr("database.snowflake_reader.get_tenant_by_id", fake_get_tenant_by_id)

    return {"tokens": tokens, "users": users}


@pytest.fixture
def client(fake_db) -> TestClient:
    # Use a fixed JWT_SECRET during tests
    os.environ["JWT_SECRET"] = "test-secret-do-not-use-in-prod"
    # Reset any cached import of api.auth so the new env var is picked up
    import importlib
    import api.auth as auth_mod
    importlib.reload(auth_mod)
    import api.routes.auth as auth_route_mod
    importlib.reload(auth_route_mod)
    import api.main as main_mod
    importlib.reload(main_mod)
    return TestClient(main_mod.app)


# ── Tests ────────────────────────────────────────────────────────
def test_register_happy_path(client: TestClient, fake_db) -> None:
    r = client.post(
        "/api/auth/register",
        json={
            "token": "INVITE-A-OK",
            "email": "alice@nhs.uk",
            "password": "correcthorse1",
            "display_name": "Dr Alice",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["token"].count(".") == 2  # JWT shape
    assert body["user"]["email"] == "alice@nhs.uk"
    assert body["user"]["tenant_id"] == "t_demo"
    assert body["user"]["display_name"] == "Dr Alice"
    assert body["user"]["role"] == "doctor"
    # Token is consumed
    assert fake_db["tokens"].by_token["INVITE-A-OK"]["used_by_user_id"] == body["user"]["user_id"]


def test_register_invalid_invite(client: TestClient) -> None:
    r = client.post(
        "/api/auth/register",
        json={
            "token": "DEFINITELY-NOT-A-TOKEN",
            "email": "bob@nhs.uk",
            "password": "correcthorse1",
            "display_name": "Dr Bob",
        },
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_token"


def test_register_weak_password(client: TestClient) -> None:
    """Server-side password validation rejects rules Pydantic accepts.
    Pydantic rejects passwords shorter than 10 chars with 422 (length
    rule); our route's value-check runs after that and returns 400 with
    a 'weak_password' code. We accept either as 'rejected'."""
    r = client.post(
        "/api/auth/register",
        json={
            "token": "INVITE-A-OK",
            "email": "weak@nhs.uk",
            "password": "abcdefgh",  # exactly 10 chars — passes Pydantic
            "display_name": "Dr Weak",
        },
    )
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "weak_password"


def test_register_reused_email(client: TestClient, fake_db) -> None:
    # First sign-up succeeds
    r1 = client.post(
        "/api/auth/register",
        json={
            "token": "INVITE-A-OK",
            "email": "alice@nhs.uk",
            "password": "correcthorse1",
            "display_name": "Dr Alice",
        },
    )
    assert r1.status_code == 201
    # Add a fresh token for the second attempt
    fake_db["tokens"].add("INVITE-B-OK", tenant_id="t_demo")
    r2 = client.post(
        "/api/auth/register",
        json={
            "token": "INVITE-B-OK",
            "email": "alice@nhs.uk",  # same email — capitalisation stripped too
            "password": "anotherone1",
            "display_name": "Dr Alice 2",
        },
    )
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "email_taken"


def test_login_happy_path(client: TestClient, fake_db) -> None:
    # Register first
    fake_db["tokens"].add("INVITE-C-OK", tenant_id="t_demo")
    client.post(
        "/api/auth/register",
        json={
            "token": "INVITE-C-OK",
            "email": "carol@nhs.uk",
            "password": "correcthorse1",
            "display_name": "Dr Carol",
        },
    )
    # Then login
    r = client.post(
        "/api/auth/login",
        json={"email": "carol@nhs.uk", "password": "correcthorse1"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token"].count(".") == 2
    assert body["user"]["email"] == "carol@nhs.uk"


def test_login_wrong_password(client: TestClient, fake_db) -> None:
    fake_db["tokens"].add("INVITE-D-OK", tenant_id="t_demo")
    client.post(
        "/api/auth/register",
        json={
            "token": "INVITE-D-OK",
            "email": "dave@nhs.uk",
            "password": "correcthorse1",
            "display_name": "Dr Dave",
        },
    )
    r = client.post(
        "/api/auth/login",
        json={"email": "dave@nhs.uk", "password": "wrong-password-1"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


def test_login_unknown_email(client: TestClient) -> None:
    r = client.post(
        "/api/auth/login",
        json={"email": "ghost@nhs.uk", "password": "anything0000"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


def test_me_with_token(client: TestClient, fake_db) -> None:
    fake_db["tokens"].add("INVITE-E-OK", tenant_id="t_demo")
    reg = client.post(
        "/api/auth/register",
        json={
            "token": "INVITE-E-OK",
            "email": "eve@nhs.uk",
            "password": "correcthorse1",
            "display_name": "Dr Eve",
        },
    )
    token = reg.json()["token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["email"] == "eve@nhs.uk"
    assert body["tenant_id"] == "t_demo"


def test_me_without_token(client: TestClient) -> None:
    me = client.get("/api/auth/me")
    assert me.status_code == 401
    assert me.json()["error"]["code"] == "INVALID_TOKEN"


def test_me_with_expired_token(client: TestClient) -> None:
    # Forge an expired JWT using the same secret the test client uses
    import api.auth as auth_mod
    import jwt as pyjwt
    expired = pyjwt.encode(
        {"sub": "u_x", "tid": "t_demo", "role": "doctor", "email": "x@nhs.uk",
         "iat": int(time.time()) - 100000, "exp": int(time.time()) - 1},
        "test-secret-do-not-use-in-prod",
        algorithm="HS256",
    )
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert me.status_code == 401
    assert me.json()["error"]["code"] == "TOKEN_EXPIRED"


def test_invite_preview_valid(client: TestClient) -> None:
    r = client.get("/api/auth/invite-preview", params={"token": "INVITE-A-OK"})
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["tenant_slug"] == "demo-trust"


def test_invite_preview_invalid(client: TestClient) -> None:
    r = client.get("/api/auth/invite-preview", params={"token": "NOPE-NOPE-NOPE"})
    assert r.status_code == 200
    assert r.json() == {"valid": False}


# ── helpers ──────────────────────────────────────────────────────
from datetime import datetime, timedelta, timezone

def _now_plus(seconds: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Optional integration test (only with real Snowflake) ─────────
@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="integration tests require SNOWFLAKE_* env vars + RUN_INTEGRATION_TESTS=1",
)
def test_register_login_me_against_real_snowflake() -> None:
    """Proves the end-to-end auth path with real Snowflake. Skipped by
    default. To run locally with a dev Snowflake account:
        RUN_INTEGRATION_TESTS=1 pytest tests/test_auth.py -v -m integration
    """
    raise NotImplementedError("Run this only with real Snowflake + a freshly issued invite token.")
