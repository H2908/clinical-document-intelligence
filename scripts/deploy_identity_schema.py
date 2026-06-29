"""
scripts/deploy_identity_schema.py — one-shot deploy of the IDENTITY
schema (tables + 3 stored procedures) to Snowflake.

Run once after pulling this branch, and any time a new SP is added:

    python -m scripts.deploy_identity_schema

Reads SNOWFLAKE_* from .env. Idempotent: every statement is
CREATE OR REPLACE / CREATE SCHEMA IF NOT EXISTS, safe to re-run.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import snowflake.connector  # noqa: E402


SQL_FILES = [
    ROOT / "database" / "schemas" / "06_identity.sql",
    ROOT / "database" / "procedures" / "sp_register_user.sql",
    ROOT / "database" / "procedures" / "sp_authenticate_user.sql",
    ROOT / "database" / "procedures" / "sp_issue_invite_token.sql",
]


def split_statements(sql: str) -> list[str]:
    """Split a SQL file on semicolons that end a statement. Skips empty
    chunks and SQL comments. Good enough for our DDL — we don't carry
    semicolons inside SP bodies because we use $$...$$ JS bodies."""
    out: list[str] = []
    buf: list[str] = []
    for raw_line in sql.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.strip().startswith("--"):
            continue
        buf.append(line)
        if line.rstrip().endswith(";"):
            stmt = "\n".join(buf).strip()
            stmt = stmt.rstrip(";").strip()
            if stmt:
                out.append(stmt)
            buf = []
    tail = "\n".join(buf).strip()
    if tail:
        out.append(tail.rstrip(";").strip())
    return out


def main() -> int:
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        database=os.environ.get("SNOWFLAKE_DATABASE", "clinical_db"),
        schema="identity",
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "clinical_wh"),
        role=os.environ["SNOWFLAKE_ROLE"],
    )
    cur = conn.cursor()

    # Schema + tables first (DDL needs to exist before SPs are created
    # because the SPs reference identity.invite_tokens / identity.users).
    for path in SQL_FILES:
        if not path.exists():
            print(f"[deploy] MISSING: {path}", file=sys.stderr)
            return 1
        text = path.read_text(encoding="utf-8")
        statements = split_statements(text)
        print(f"\n[deploy] {path.relative_to(ROOT)} -> {len(statements)} statement(s)")
        for i, stmt in enumerate(statements, 1):
            first_line = stmt.splitlines()[0][:80] if stmt else ""
            try:
                cur.execute(stmt)
                print(f"  [{i}/{len(statements)}] OK: {first_line}")
            except Exception as e:
                print(f"  [{i}/{len(statements)}] FAIL: {first_line}", file=sys.stderr)
                print(f"    {e}", file=sys.stderr)
                return 1

    print("\n[deploy] All identity objects deployed. Verify with:")
    print("    SHOW TABLES IN SCHEMA clinical_db.identity;")
    print("    SHOW PROCEDURES IN SCHEMA clinical_db.identity;")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        try:
            snowflake.connector.connect  # noqa
        except Exception:
            pass
