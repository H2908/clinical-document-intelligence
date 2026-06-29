-- sp_authenticate_user.sql — clinical-intelligence
-- Stored procedure: SP_AUTHENTICATE_USER
-- Returns user_id, tenant_id, password_hash, display_name, role given
-- an email. Does NOT verify the password — bcrypt verify is done in
-- api/auth.py (the hash never leaves Snowflake except as a single
-- column read for the single matching row; we keep it on the wire
-- encrypted via TLS).
--
-- Signature:
--   SP_AUTHENTICATE_USER(email STRING) RETURNS STRING
--     -> JSON {user_id, tenant_id, password_hash, display_name, role}
--     -> JSON {error: "not_found"} when email does not exist
--
-- Called by: api/routes/auth.py -> database/snowflake_writer.authenticate_user
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA identity;

CREATE OR REPLACE PROCEDURE SP_AUTHENTICATE_USER(EMAIL STRING)
RETURNS STRING
LANGUAGE JAVASCRIPT
AS
$$
    if (!EMAIL) throw new Error("email is required");
    try {
        const stmt = snowflake.createStatement({
            sqlText: `SELECT user_id, tenant_id, password_hash, display_name, role
                      FROM identity.users WHERE email = ? LIMIT 1`
        });
        stmt.setParameter(1, EMAIL.toLowerCase());
        const rs = stmt.execute().getResultSet();
        if (!rs.next()) {
            return JSON.stringify({error: "not_found"});
        }
        return JSON.stringify({
            user_id:       rs.getColumnValue("USER_ID"),
            tenant_id:     rs.getColumnValue("TENANT_ID"),
            password_hash: rs.getColumnValue("PASSWORD_HASH"),
            display_name:  rs.getColumnValue("DISPLAY_NAME"),
            role:          rs.getColumnValue("ROLE")
        });
    } catch (e) {
        return JSON.stringify({error: "internal_error", message: e.toString()});
    }
$$;
