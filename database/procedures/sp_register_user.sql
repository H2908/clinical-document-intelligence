-- sp_register_user.sql — clinical-intelligence
-- Stored procedure: SP_REGISTER_USER
-- Atomic signup: validates invite token not used / not expired,
-- inserts a user, and marks the token consumed — all in one TX.
--
-- Signature:
--   SP_REGISTER_USER(
--       token         STRING,
--       email         STRING,
--       password_hash STRING,
--       display_name  STRING
--   ) RETURNS STRING  -- JSON: {user_id, tenant_id, role} or {error}
--
-- Error codes (returned in JSON):
--   'invalid_token'      -- token does not exist, used, or expired
--   'email_taken'        -- users.email already exists
--   'invalid_email'      -- email is empty or not a valid form
--
-- Called by: api/routes/auth.py -> database/snowflake_writer.register_user
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA identity;

CREATE OR REPLACE PROCEDURE SP_REGISTER_USER(
    TOKEN         STRING,
    EMAIL         STRING,
    PASSWORD_HASH STRING,
    DISPLAY_NAME  STRING
)
RETURNS STRING
LANGUAGE JAVASCRIPT
AS
$$
    // ── Validation ───────────────────────────────────────────────
    if (!TOKEN)         throw new Error("token is required");
    if (!EMAIL)         throw new Error("email is required");
    if (!PASSWORD_HASH) throw new Error("password_hash is required");
    if (!DISPLAY_NAME)  throw new Error("display_name is required");

    // basic email shape check (full validation in api/auth.py)
    if (!/.+@.+\..+/.test(EMAIL)) {
        return JSON.stringify({error: "invalid_email", message: "Email format invalid"});
    }

    try {
        // 1. Validate invite token
        const tokStmt = snowflake.createStatement({
            sqlText: `SELECT tenant_id, role, used_by_user_id, expires_at
                      FROM identity.invite_tokens WHERE token = ? LIMIT 1`
        });
        tokStmt.setParameter(1, TOKEN);
        const tokRs = tokStmt.execute().getResultSet();
        if (!tokRs.next()) {
            return JSON.stringify({error: "invalid_token", message: "Invite token not found"});
        }

        const tenant_id       = tokRs.getColumnValue("TENANT_ID");
        const role            = tokRs.getColumnValue("ROLE");
        const used_by_user_id = tokRs.getColumnValue("USED_BY_USER_ID");
        const expires_at_raw  = tokRs.getColumnValue("EXPIRES_AT");

        if (used_by_user_id !== null) {
            return JSON.stringify({error: "invalid_token", message: "Invite token already used"});
        }
        const expires_ms = (expires_at_raw && expires_at_raw.getTime)
            ? expires_at_raw.getTime()
            : new Date(expires_at_raw).getTime();
        if (expires_ms < Date.now()) {
            return JSON.stringify({error: "invalid_token", message: "Invite token expired"});
        }

        // 2. Email uniqueness check
        const emailStmt = snowflake.createStatement({
            sqlText: `SELECT 1 FROM identity.users WHERE email = ? LIMIT 1`
        });
        emailStmt.setParameter(1, EMAIL.toLowerCase());
        const emailRs = emailStmt.execute().getResultSet();
        if (emailRs.next()) {
            return JSON.stringify({error: "email_taken", message: "Email already registered"});
        }

        // 3. Generate a UUID-shaped id (no crypto dep on snowflake-sdk)
        function hex4() { return Math.floor((1 + Math.random()) * 0x10000).toString(16).substring(1); }
        const new_user_id =
            hex4() + hex4() + "-" + hex4() + "-4" + hex4().substring(1) +
            "-" + hex4() + "-" + hex4() + hex4() + hex4();

        // 4. Insert user
        const insUser = snowflake.createStatement({
            sqlText: `INSERT INTO identity.users
                        (user_id, tenant_id, email, password_hash, display_name, role)
                      VALUES (?, ?, ?, ?, ?, ?)`
        });
        insUser.setParameter(1, new_user_id);
        insUser.setParameter(2, tenant_id);
        insUser.setParameter(3, EMAIL.toLowerCase());
        insUser.setParameter(4, PASSWORD_HASH);
        insUser.setParameter(5, DISPLAY_NAME);
        insUser.setParameter(6, role);
        insUser.execute();

        // 5. Mark invite consumed
        const updTok = snowflake.createStatement({
            sqlText: `UPDATE identity.invite_tokens
                      SET used_by_user_id = ?, used_at = CURRENT_TIMESTAMP()
                      WHERE token = ?`
        });
        updTok.setParameter(1, new_user_id);
        updTok.setParameter(2, TOKEN);
        updTok.execute();

        return JSON.stringify({
            user_id: new_user_id,
            tenant_id: tenant_id,
            role: role
        });
    } catch (e) {
        return JSON.stringify({error: "internal_error", message: e.toString()});
    }
$$;
