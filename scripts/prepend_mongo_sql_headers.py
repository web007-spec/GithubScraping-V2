#!/usr/bin/env python3
"""Prepend MongoDB redirect header to schema/*.sql (Postgres-only legacy files)."""

from pathlib import Path

HEADER = """\
-- =============================================================================
-- MongoDB (DATABASE_STORAGE=mongodb): DO NOT run this SQL file.
-- Apply full schema:  python scripts/apply_mongodb_schema.py
-- Per-module script:  schema/mongodb/{stem}.mongodb.js
-- See schema/mongodb/README.md for mapping.
-- =============================================================================

"""

root = Path(__file__).resolve().parents[1] / "schema"
for path in sorted(root.glob("*.sql")):
    text = path.read_text(encoding="utf-8")
    stem = path.stem
    header = HEADER.format(stem=stem)
    if "MongoDB (DATABASE_STORAGE=mongodb)" in text[:800]:
        # Refresh header if stem line missing
        if f"schema/mongodb/{stem}.mongodb.js" in text[:800]:
            print("skip", path.name)
            continue
        # Strip old header (first 7 lines block)
        lines = text.splitlines(keepends=True)
        body_start = 0
        for i, line in enumerate(lines):
            if line.startswith("-- Requires:") or line.startswith("-- Run in") or line.startswith("CREATE "):
                body_start = i
                break
            if i > 0 and not line.startswith("--") and line.strip():
                body_start = i
                break
        text = "".join(lines[body_start:])
    path.write_text(header + text, encoding="utf-8")
    print("updated", path.name)
