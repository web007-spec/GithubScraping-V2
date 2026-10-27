"""Run scrape jobs outside the API process.

Keeping the scraper in a separate Python process prevents heavy GitHub/Supabase
work from resetting or starving the FastAPI socket used by the frontend proxy.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from app.services.run_stop import clear_run, register_run

log = logging.getLogger(__name__)

_processes: dict[str, subprocess.Popen] = {}
_lock = threading.Lock()

BACKEND_ROOT = Path(__file__).resolve().parents[2]
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000


def _encoded_config(config: dict[str, Any]) -> str:
    raw = json.dumps(config, separators=(",", ":"), default=str).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _cleanup_locked() -> None:
    dead = [run_id for run_id, proc in _processes.items() if proc.poll() is not None]
    for run_id in dead:
        _processes.pop(run_id, None)
        clear_run(run_id)


def start_scrape_run(run_id: str, config: dict[str, Any]) -> str:
    """Start scrape in a child process. Returns the child process id."""
    register_run(run_id)
    encoded = _encoded_config(config)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND_ROOT)

    cmd = [
        sys.executable,
        "-m",
        "app.services.scrape_worker",
        run_id,
        encoded,
    ]

    creationflags = 0
    if os.name == "nt":
        creationflags |= BELOW_NORMAL_PRIORITY_CLASS

    with _lock:
        _cleanup_locked()
        proc = _processes.get(run_id)
        if proc is not None and proc.poll() is None:
            raise RuntimeError(f"Run {run_id} is already executing")

        proc = subprocess.Popen(
            cmd,
            cwd=str(BACKEND_ROOT),
            env=env,
            creationflags=creationflags,
        )
        _processes[run_id] = proc

    log.info("Started scrape run %s in child process %s", run_id, proc.pid)
    return str(proc.pid)


def is_run_active(run_id: str) -> bool:
    with _lock:
        _cleanup_locked()
        proc = _processes.get(run_id)
        return proc is not None and proc.poll() is None


def has_active_scrapes() -> bool:
    with _lock:
        _cleanup_locked()
        return any(proc.poll() is None for proc in _processes.values())


def terminate_run(run_id: str) -> None:
    with _lock:
        proc = _processes.get(run_id)
        if proc is None or proc.poll() is not None:
            _processes.pop(run_id, None)
            clear_run(run_id)
            return
        log.warning("Terminating scrape child process %s for run %s", proc.pid, run_id)
        proc.terminate()
