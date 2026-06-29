"""
scripts/issue_invite.py — admin-side: issue one invite token for a tenant.

Usage:
    python -m scripts.issue_invite --tenant demo-trust --role doctor
    python -m scripts.issue_invite --tenant demo-trust --role admin --ttl 2592000

The script prints the token and a deep link the admin can paste into
a welcome email / WhatsApp message / printed slip:

    Invite token (valid 7 days):
        a8Kp2QwL9XrN4bYc7vMzT3jH6dF5gU1q

    Share with the clinician:
        https://app.nhs.uk/register?invite=a8Kp2QwL9XrN4bYc7vMzT3jG6dF5gU1q

    Local-dev link:
        http://localhost:3000/register?invite=a8Kp2QwL9XrN4bYc7vMzT3jG6dF5gU1q

Requires SNOWFLAKE_* env vars (sourced from .env via python-dotenv).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add repo root to sys.path so `database.snowflake_writer` resolves.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")


def main() -> int:
    p = argparse.ArgumentParser(
        description="Issue a fresh invite token for a tenant. Admin-only."
    )
    p.add_argument(
        "--tenant",
        required=True,
        help="Tenant slug (e.g. 'demo-trust', 'kings-college') OR tenant_id.",
    )
    p.add_argument(
        "--role",
        default="doctor",
        choices=["doctor", "admin"],
        help="Role assigned to whoever consumes this token (default: doctor).",
    )
    p.add_argument(
        "--ttl",
        type=int,
        default=7 * 24 * 3600,
        help="Token lifetime in seconds (default: 7 days).",
    )
    p.add_argument(
        "--app-url",
        default=os.environ.get("PUBLIC_APP_URL", "http://localhost:3000"),
        help="Base URL the user will visit (for the magic link). Default: localhost.",
    )
    args = p.parse_args()

    # Resolve slug -> tenant_id (or pass through if already a UUID-shaped id).
    from database import snowflake_reader, snowflake_writer  # noqa: E402

    tenant = snowflake_reader.get_tenant_by_slug(args.tenant)
    if tenant is None:
        # Allow passing tenant_id directly.
        tenant = snowflake_reader.get_tenant_by_id(args.tenant)
    if tenant is None:
        print(
            f"[issue_invite] Tenant '{args.tenant}' not found. "
            f"Run `python -m scripts.seed_tenant --slug {args.tenant} --name '...'` first.",
            file=sys.stderr,
        )
        return 2

    result = snowflake_writer.issue_invite_token(
        tenant_id=tenant["tenant_id"],
        role=args.role,
        ttl_seconds=args.ttl,
    )
    if "error" in result:
        print(f"[issue_invite] Failed: {result['error']} — {result.get('message')}",
              file=sys.stderr)
        return 1

    token = result["token"]
    expires_at = result.get("expires_at", "(unknown)")
    print(f"\nInvite token for tenant '{tenant['name']}' (role: {args.role})")
    print(f"Valid until: {expires_at}\n")
    print(f"    {token}\n")
    print("Share this token with the new clinician. They can paste it at /register,")
    print(f"or click the link below:\n")
    print(f"    {args.app_url}/register?invite={token}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
