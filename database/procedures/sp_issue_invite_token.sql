-- sp_issue_invite_token.sql — clinical-intelligence
-- Stored procedure: SP_ISSUE_INVITE_TOKEN
-- Admin-side: create a fresh invite token bound to a tenant.
--
-- Signature:
--   SP_ISSUE_INVITE_TOKEN(
--       tenant_id   STRING,
--       role        STRING,   -- 'doctor' (default) or 'admin'
--       ttl_seconds NUMBER    -- default 604800 (7 days)
--   ) RETURNS STRING
--     -> JSON {token, tenant_id, role, expires_at}
--     -> JSON {error, message} on failure
--
-- Called by: scripts/issue_invite.py via database.snowflake_writer
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
    const r = (ROLE && ROLE.length > 0) ? ROLE : "doctor";
    const ttl = TTL_SECONDS ? TTL_SECONDS : 604800;

    // 32-char URL-safe random token
    const ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    let token = "";
    for (let i = 0; i < 32; i++) {
        token += ALPHA.charAt(Math.floor(Math.random() * ALPHA.length));
    }

    try {
        // Insert with computed expires_at, then read it back via the same
        // statement so we return the value the row actually holds.
        const ins = snowflake.createStatement({
            sqlText: `INSERT INTO identity.invite_tokens
                        (token, tenant_id, role, expires_at)
                      SELECT ?, ?, ?, DATEADD('second', ?, CURRENT_TIMESTAMP())`
        });
        ins.setParameter(1, token);
        ins.setParameter(2, TENANT_ID);
        ins.setParameter(3, r);
        ins.setParameter(4, ttl);
        ins.execute();

        const sel = snowflake.createStatement({
            sqlText: `SELECT expires_at FROM identity.invite_tokens WHERE token = ?`
        });
        sel.setParameter(1, token);
        const rs = sel.execute().getResultSet();
        if (!rs.next()) {
            return JSON.stringify({error: "internal_error", message: "Insert succeeded but row not found"});
        }
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
