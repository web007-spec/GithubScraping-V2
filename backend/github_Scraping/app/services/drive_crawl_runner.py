"""Start and monitor Google Drive crawl subprocesses."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from app.config import get_settings

log = logging.getLogger(__name__)

INDEXER_ROOT = Path(__file__).resolve().parents[3] / "google_drive_indexer"
WORKER_SCRIPT = INDEXER_ROOT / "run_crawl_job.py"
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000

_processes: dict[str, subprocess.Popen] = {}
_watchers: dict[str, threading.Thread] = {}
_lock = threading.Lock()


def _cleanup_locked() -> None:
    dead = [run_id for run_id, proc in _processes.items() if proc.poll() is not None]
    for run_id in dead:
        _processes.pop(run_id, None)
        _watchers.pop(run_id, None)


def _mark_worker_exit(run_id: str, exit_code: int) -> None:
    from app.services.drive_crawl_runs import mark_worker_exit

    try:
        mark_worker_exit(run_id, exit_code)
    except Exception:
        log.exception("Failed to record drive worker exit for %s", run_id)


def _watch_worker(run_id: str, proc: subprocess.Popen) -> None:
    code = proc.wait()
    with _lock:
        _processes.pop(run_id, None)
        _watchers.pop(run_id, None)
    if code != 0:
        _mark_worker_exit(run_id, code)


def _worker_env() -> dict[str, str]:
    settings = get_settings()
    env = os.environ.copy()
    backend_root = str(INDEXER_ROOT.parent)
    env["PYTHONPATH"] = os.pathsep.join([str(INDEXER_ROOT), backend_root])
    env["MONGODB_URI"] = settings.mongodb_uri
    env["MONGODB_DB_NAME"] = settings.mongodb_db_name
    env["DATABASE_STORAGE"] = "mongodb"
    return env


def _worker_python() -> str:
    if os.name == "nt":
        candidates = (
            INDEXER_ROOT / ".venv" / "Scripts" / "python.exe",
            INDEXER_ROOT / "venv" / "Scripts" / "python.exe",
        )
    else:
        candidates = (
            INDEXER_ROOT / ".venv" / "bin" / "python",
            INDEXER_ROOT / "venv" / "bin" / "python",
        )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def verify_worker_runtime() -> None:
    """Fail fast when the indexer venv is missing required packages."""
    python = _worker_python()
    check = subprocess.run(
        [
            python,
            "-c",
            "import loguru, ddgs, aiohttp, bs4, pymongo  # noqa: F401",
        ],
        cwd=str(INDEXER_ROOT),
        env=_worker_env(),
        capture_output=True,
        text=True,
    )
    if check.returncode != 0:
        detail = (check.stderr or check.stdout or "").strip()
        raise RuntimeError(
            "Google Drive indexer dependencies are not installed. "
            "Run: .\\start-project.ps1 -Install "
            f"(or: cd backend\\google_drive_indexer && .venv\\Scripts\\pip install -r requirements.txt). "
            f"{detail}"
        )


def start_drive_crawl(run_id: str) -> str:
    if not WORKER_SCRIPT.is_file():
        raise RuntimeError(f"Drive crawl worker not found: {WORKER_SCRIPT}")

    verify_worker_runtime()

    cmd = [_worker_python(), str(WORKER_SCRIPT), run_id]
    creationflags = 0
    if os.name == "nt":
        creationflags |= BELOW_NORMAL_PRIORITY_CLASS

    with _lock:
        _cleanup_locked()
        proc = _processes.get(run_id)
        if proc is not None and proc.poll() is None:
            raise RuntimeError(f"Drive crawl run {run_id} is already executing")

        proc = subprocess.Popen(
            cmd,
            cwd=str(INDEXER_ROOT),
            env=_worker_env(),
            creationflags=creationflags,
        )
        _processes[run_id] = proc
        watcher = threading.Thread(
            target=_watch_worker, args=(run_id, proc), daemon=True, name=f"drive-crawl-{run_id[:8]}"
        )
        _watchers[run_id] = watcher
        watcher.start()

    log.info("Started Google Drive crawl %s in child process %s", run_id, proc.pid)
    return str(proc.pid)


def is_crawl_active(run_id: str) -> bool:
    with _lock:
        _cleanup_locked()
        proc = _processes.get(run_id)
        return proc is not None and proc.poll() is None


def terminate_crawl(run_id: str) -> None:
    with _lock:
        proc = _processes.get(run_id)
        if proc is None or proc.poll() is not None:
            _processes.pop(run_id, None)
            return
        log.warning("Terminating drive crawl process %s for run %s", proc.pid, run_id)
        proc.terminate()


def heal_run_status(run_id: str, row: dict[str, Any]) -> dict[str, Any]:
    status = str(row.get("status") or "")
    if status not in ("pending", "running", "stopping"):
        return row
    if is_crawl_active(run_id):
        return row
    if status == "stopping":
        return {**row, "status": "stopped"}
    return {**row, "status": "failed", "last_error": row.get("last_error") or "Worker exited unexpectedly"}
