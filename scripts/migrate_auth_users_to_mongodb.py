#!/usr/bin/env python3
"""Import Supabase Auth users into MongoDB auth_users (optional one-time step)."""

import argparse
import logging
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
API_ROOT = BACKEND / "github_Scraping"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(API_ROOT))


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv(BACKEND / "github_Scraping" / ".env")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Import Supabase auth users to MongoDB")
    parser.add_argument(
        "--default-password",
        help="Set this password for imported users (they should change it after first login)",
    )
    args = parser.parse_args()

    import os

    from supabase import create_client

    from app.services.local_auth import import_user_from_supabase

    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required for import")

    sb = create_client(url, key)
    page = 1
    imported = 0
    while True:
        response = sb.auth.admin.list_users(page=page, per_page=200)
        batch = getattr(response, "users", None)
        if batch is None and isinstance(response, dict):
            batch = response.get("users") or []
        if batch is None:
            batch = list(response) if response else []
        if not batch:
            break
        for user in batch:
            meta = getattr(user, "user_metadata", None) or {}
            app_meta = getattr(user, "app_metadata", None) or {}
            import_user_from_supabase(
                user_id=str(user.id),
                email=str(user.email or ""),
                role=str(app_meta.get("role") or "admin"),
                user_metadata=meta if isinstance(meta, dict) else {},
                password=args.default_password,
            )
            imported += 1
        if len(batch) < 200:
            break
        page += 1

    print(f"Imported {imported} auth user(s) into MongoDB auth_users")
    if args.default_password:
        print("Users can sign in with their email and the --default-password you provided.")


if __name__ == "__main__":
    main()
