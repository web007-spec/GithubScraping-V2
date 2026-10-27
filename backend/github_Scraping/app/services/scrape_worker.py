"""Child-process entry point for scrape jobs."""

from __future__ import annotations

import base64
import json
import logging
import sys

from app.services.scrape_job import execute_scrape_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def _decode_config(value: str) -> dict:
    raw = base64.urlsafe_b64decode(value.encode("ascii"))
    return json.loads(raw.decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        print("Usage: python -m app.services.scrape_worker RUN_ID BASE64_CONFIG", file=sys.stderr)
        return 2

    run_id, encoded_config = args
    try:
        execute_scrape_run(run_id, _decode_config(encoded_config))
        return 0
    except Exception:
        log.exception("Scrape worker failed for run %s", run_id)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
