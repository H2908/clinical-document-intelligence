-- sp_issue_invite_token.sql — clinical-intelligence
-- Stored procedure: SP_ISSUE_INVITE_TOKEN
-- Admin-side: create a fresh invite token, optionally pre-bound to a
-- tenant_id (admin supplies) or just to a tenant_slug (caller looks
-- up the tenant_id first).
--
-- Signature:
--   SP_ISSUE_INVITE_TOKEN(
--       tenant_id   STRING,
--       role        STRING,   -- 'doctor' (default) or 'admin'
--       ttl_seconds NUMBER    -- default 604800 (7 days)
--   ) RETURNS STRING
--     -> JSON {token, tenant_id, role, expires_at}
--
-- Called by: admin script (script/seed_invite.py).
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA identity;

CREATE OR REPLACE PROCEDURE SP_ISSUE_INVITE_TOKEN(
    TENANT_ID   STRING,
    ROLE        STRING,
    TTL_SECONDS NUMBER
)
RETURNS STRING
LANGUAGE JAVASCRIPT
AS
$$
    if (!TENANT_ID) throw new Error("tenant_id is required");
    const r = ROLE || 'doctor';
    const ttl = TTL_SECONDS || 604800;

    // 32-char URL-safe random token
    const ALPHA = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let token = '';
    for (let i = 0; i < 32; i++) {
        token += ALPHA.charAt(Math.floor(Math.random() * ALPHA.length));
    }

    try {
        const ins = snowflake.createStatement({
            sqlText: `INSERT INTO identity.invite_tokens
                        (token, tenant_id, role, expires_at)
                      VALUES (?, ?, ?, DATEADD('second', ?, CURRENT_TIMESTAMP()))`
        });
        ins.setParameter(1, token);
        ins.setParameter(2, TENANT_ID);
        ins.setParameter(3, r);
        ins.setParameter(4, ttl);
        ins.execute();

        const exp = snowflake.createStatement({
            sqlText: `SELECT DATEADD('second', ?, CURRENT_TIMESTAMP()) AS expires_at`
        });
        exp.setParameter(1, ttl);
        const rs = exp.execute().getResultSet();
        rs.next();
        const expires_at = rs.getColumnValue("EXPIRES_AT");

        return JSON.stringify({
            token: token,
            tenant_id: TENANT_ID,
            role: r,
            expires_at: expires_at
        });
    } catch (e) {
        return JSON.stringify({error: "internal_error", message: e.toString()});
    }
$$;
