#!/usr/bin/env python3
"""Apply MongoDB schema (indexes) — equivalent to running schema/mongodb/setup.mongodb.js."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

log = logging.getLogger(__name__)


def _load_env() -> None:
    from dotenv import load_dotenv

    api_env = BACKEND / "github_Scraping" / ".env"
    if api_env.is_file():
        load_dotenv(api_env)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Apply Outreach Console MongoDB schema")
    parser.add_argument(
        "--rebuild-country-stats",
        action="store_true",
        help="Rebuild github_user_country_stats from github_users (replaces SQL trigger)",
    )
    args = parser.parse_args()

    _load_env()
    from outreach_db.client import get_database, mongodb_db_name, ping
    from outreach_db.mongodb_schema import apply_schema, rebuild_country_stats

    if not ping():
        print("Cannot connect to MongoDB. Set MONGODB_URI and start mongod.", file=sys.stderr)
        return 1

    db = get_database()
    print(f"Applying schema to database: {mongodb_db_name()}")
    counts = apply_schema(db)
    total = sum(counts.values())
    for name, n in sorted(counts.items()):
        print(f"  {name}: {n} index(es)")
    print(f"  TOTAL: {total} index operations")

    if args.rebuild_country_stats:
        n = rebuild_country_stats(db)
        print(f"Rebuilt github_user_country_stats: {n} countries")

    print("MongoDB schema applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
