"""
scripts/seed_tenant.py — admin-side: insert one tenant row into identity.tenants.

Usage:
    python -m scripts.seed_tenant --slug demo-trust --name "Demo NHS Trust"
    python -m scripts.seed_tenant --slug kings --name "King's College Hospital NHS Trust" --tenant-id t_kings

Then issue an invite for the new tenant:
    python -m scripts.issue_invite --tenant demo-trust --role admin

Requires SNOWFLAKE_* env vars.
"""
from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")


def main() -> int:
    p = argparse.ArgumentParser(description="Seed one tenant row into identity.tenants.")
    p.add_argument("--slug", required=True, help="URL-safe slug, e.g. 'demo-trust'")
    p.add_argument("--name", required=True, help="Display name, e.g. 'Demo NHS Trust'")
    p.add_argument(
        "--tenant-id",
        default=None,
        help="Optional explicit UUID. Default: derived from slug with a random suffix.",
    )
    args = p.parse_args()

    from database import snowflake_reader, snowflake_writer  # noqa: E402

    if snowflake_reader.get_tenant_by_slug(args.slug) is not None:
        print(f"[seed_tenant] Tenant with slug '{args.slug}' already exists.", file=sys.stderr)
        return 1

    tenant_id = args.tenant_id or f"t_{args.slug.replace('-', '_')}_{secrets.token_hex(3)}"

    try:
        snowflake_writer.create_tenant(
            tenant_id=tenant_id,
            slug=args.slug,
            name=args.name,
        )
    except Exception as e:
        print(f"[seed_tenant] Failed: {e}", file=sys.stderr)
        return 1

    print(f"\nSeeded tenant:\n")
    print(f"    tenant_id : {tenant_id}")
    print(f"    slug      : {args.slug}")
    print(f"    name      : {args.name}\n")
    print(f"Next: python -m scripts.issue_invite --tenant {args.slug} --role admin\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
