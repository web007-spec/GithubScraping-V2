#!/usr/bin/env python3
"""Migrate all Supabase application tables into MongoDB."""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from outreach_db.migrate import main

if __name__ == "__main__":
    main()
