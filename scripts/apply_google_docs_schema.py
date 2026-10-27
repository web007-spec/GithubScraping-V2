#!/usr/bin/env python3
"""Apply schema/google_docs_setup.sql to Supabase Postgres."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend" / "github_Scraping"
sys.path.insert(0, str(BACKEND))

from app.services.google_docs_schema import apply_google_docs_schema  # noqa: E402


def _load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        values[key.strip()] = val.strip()
    return values


def main() -> int:
    env = _load_env(BACKEND / ".env")
    supabase_url = env.get("SUPABASE_URL", "")
    if not supabase_url:
        print("Set SUPABASE_URL in backend/github_Scraping/.env", file=sys.stderr)
        return 1
    try:
        result = apply_google_docs_schema(
            supabase_url=supabase_url,
            db_password=env.get("SUPABASE_DB_PASSWORD", ""),
            database_url=env.get("DATABASE_URL", "") or env.get("SUPABASE_DATABASE_URL", ""),
        )
        print("OK", result)
        return 0 if not result.get("still_missing") else 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        ref = supabase_url.replace("https://", "").split(".")[0]
        print(
            f"\nManual fix:\n"
            f"1. Open https://supabase.com/dashboard/project/{ref}/sql/new\n"
            f"2. Paste and run the contents of schema/google_docs_setup.sql",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
