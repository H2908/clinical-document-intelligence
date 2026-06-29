-- 06_identity.sql — clinical-intelligence
-- IDENTITY layer: tenants, users, invite tokens.
-- Run AFTER 03_core.sql.
--
-- Schema: clinical_db.identity
--
-- Tables (3):
--   1. tenants       — one row per NHS trust/hospital
--   2. users         — clinicians and admins, each bound to one tenant
--   3. invite_tokens — pre-issued tokens that bind new signups to a tenant
--
-- Design notes:
--   - All IDs are STRING UUIDs (matches CONTRACT.md §1 type convention).
--   - email is UNIQUE globally so login is a simple SELECT.
--   - password_hash stores a bcrypt hash (cost factor 12, ASCII-encoded).
--   - invite_tokens.token is a 32-char URL-safe random string, UNIQUE.
--   - used_by_user_id is filled when SP_REGISTER_USER consumes the token.
--   - tenant_id is STRING-typed but does NOT carry a FK constraint
--     to the new tenants table because Snowflake does not enforce
--     FKs. The application layer (api/auth.py) ensures integrity.
--
-- Owner: Member A (DE) — Review needed.
-- Reviewed-by: Member B (ML) — auth wiring lives in api/auth.py.
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
CREATE SCHEMA IF NOT EXISTS identity;
USE SCHEMA identity;

-- ── 1. tenants ───────────────────────────────────────────────────
create or replace table tenants (
    tenant_id    string primary key,
    slug         string unique not null,    -- e.g. 'demo-trust', 'kings-college'
    name         string not null,           -- 'King's College Hospital NHS Trust'
    created_at   timestamp_ntz default current_timestamp()
);

-- ── 2. users ─────────────────────────────────────────────────────
create or replace table users (
    user_id        string primary key,
    tenant_id      string not null,          -- logical FK -> tenants.tenant_id
    email          string unique not null,
    password_hash  string not null,          -- bcrypt
    display_name   string not null,
    role           string not null default 'doctor',  -- 'doctor' | 'admin'
    created_at     timestamp_ntz default current_timestamp(),
    last_login_at  timestamp_ntz
);

-- ── 3. invite_tokens ─────────────────────────────────────────────
create or replace table invite_tokens (
    token             string primary key,    -- 32-char URL-safe random
    tenant_id         string not null,
    role              string not null default 'doctor',
    used_by_user_id   string,                -- null until consumed
    expires_at        timestamp_ntz not null,
    used_at           timestamp_ntz,
    created_at        timestamp_ntz default current_timestamp(),
    created_by        string                 -- admin user_id who issued
);

-- Note: tenant_id uniqueness on active (unused) tokens is enforced by
-- the issue_invite_token SP via SELECT-then-INSERT — multiple unused
-- tokens per tenant are allowed but only one consumed per actual signup.
