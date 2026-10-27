"""Apply Google Docs Supabase schema via direct Postgres connection."""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from urllib.parse import quote_plus, urlparse

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
SETUP_SQL = REPO_ROOT / "schema" / "google_docs_setup.sql"


def _extract_project_ref(supabase_url: str) -> str | None:
    try:
        host = urlparse(supabase_url.strip()).netloc
        match = re.match(r"^([a-z0-9]+)\.supabase\.co$", host, re.I)
        return match.group(1) if match else None
    except Exception:
        return None


def build_database_url(
    *,
    supabase_url: str,
    db_password: str,
    database_url: str = "",
) -> str:
    if database_url.strip():
        url = database_url.strip()
        if url.startswith("postgresql+asyncpg://"):
            url = "postgresql://" + url.split("://", 1)[1]
        return url

    ref = _extract_project_ref(supabase_url)
    if not ref:
        raise ValueError(f"Could not parse Supabase project ref from {supabase_url}")
    if not db_password.strip():
        raise ValueError(
            "Database password required. Set SUPABASE_DB_PASSWORD in backend/.env "
            "(Supabase Dashboard → Project Settings → Database → Database password)."
        )
    user = "postgres"
    password = quote_plus(db_password.strip())
    return f"postgresql://{user}:{password}@db.{ref}.supabase.co:5432/postgres"


def tables_missing(conn) -> list[str]:
    missing: list[str] = []
    with conn.cursor() as cur:
        for table in ("google_documents", "google_docs_crawl_runs"):
            cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
            if cur.fetchone()[0] is None:
                missing.append(table)
    return missing


def apply_google_docs_schema(
    *,
    supabase_url: str,
    db_password: str = "",
    database_url: str = "",
) -> dict:
    import psycopg2

    if not SETUP_SQL.is_file():
        raise FileNotFoundError(f"Schema file not found: {SETUP_SQL}")

    dsn = build_database_url(
        supabase_url=supabase_url,
        db_password=db_password,
        database_url=database_url,
    )
    sql = SETUP_SQL.read_text(encoding="utf-8")

    with psycopg2.connect(dsn) as conn:
        conn.autocommit = True
        before = tables_missing(conn)
        with conn.cursor() as cur:
            cur.execute(sql)
        after = tables_missing(conn)

    created = [t for t in before if t not in after]
    return {
        "ok": True,
        "created_tables": created,
        "still_missing": after,
        "sql_file": str(SETUP_SQL),
    }


def check_google_docs_schema(*, supabase_url: str, db_password: str = "", database_url: str = "") -> dict:
    import psycopg2

    dsn = build_database_url(
        supabase_url=supabase_url,
        db_password=db_password,
        database_url=database_url,
    )
    with psycopg2.connect(dsn) as conn:
        missing = tables_missing(conn)
    return {"ok": not missing, "missing_tables": missing}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    backend_env = REPO_ROOT / "backend" / "github_Scraping" / ".env"
    values: dict[str, str] = {}
    if backend_env.is_file():
        for line in backend_env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            values[key.strip()] = val.strip()

    supabase_url = values.get("SUPABASE_URL") or ""
    db_password = values.get("SUPABASE_DB_PASSWORD") or ""
    database_url = values.get("DATABASE_URL") or values.get("SUPABASE_DATABASE_URL") or ""

    if not supabase_url:
        print("SUPABASE_URL missing in backend/github_Scraping/.env", file=sys.stderr)
        sys.exit(1)

    try:
        result = apply_google_docs_schema(
            supabase_url=supabase_url,
            db_password=db_password,
            database_url=database_url,
        )
        print("Schema applied successfully.")
        if result["created_tables"]:
            print("Created tables:", ", ".join(result["created_tables"]))
        if result["still_missing"]:
            print("Still missing:", ", ".join(result["still_missing"]))
            sys.exit(1)
    except Exception as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        print("\nManual fix: open Supabase SQL Editor and run schema/google_docs_setup.sql", file=sys.stderr)
        sys.exit(1)
