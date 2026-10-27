"""Start and monitor Google Docs crawl subprocesses."""

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

INDEXER_ROOT = Path(__file__).resolve().parents[3] / "google_docs_indexer"
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
    """Update crawl run when the child exits without finishing normally."""
    from app.services.docs_crawl_runs import mark_worker_exit

    try:
        mark_worker_exit(run_id, exit_code)
    except Exception:
        log.exception("Failed to record worker exit for crawl %s", run_id)


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
    if use_mongodb_backend(settings):
        env["DATABASE_STORAGE"] = "mongodb"
        env["GOOGLE_DOCS_STORAGE"] = "mongodb"
    else:
        env["DATABASE_STORAGE"] = settings.database_storage
        env["GOOGLE_DOCS_STORAGE"] = settings.google_docs_storage
    if not use_mongodb_backend(settings):
        env["SUPABASE_URL"] = settings.supabase_url
        env["SUPABASE_SERVICE_ROLE_KEY"] = settings.supabase_service_role_key
    return env


def use_mongodb_backend(settings=None) -> bool:
    settings = settings or get_settings()
    mode = (settings.google_docs_storage or "auto").strip().lower()
    if mode == "supabase":
        return False
    if mode == "mongodb":
        return bool((settings.mongodb_uri or "").strip())
    return bool((settings.mongodb_uri or "").strip())


def _worker_python() -> str:
    """Prefer the indexer virtualenv so crawl subprocess has all dependencies."""
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


def _ensure_worker_deps() -> None:
    """Fail fast when MongoDB crawl worker Python is missing required packages."""
    if not use_mongodb_backend():
        return
    python = _worker_python()
    check = subprocess.run(
        [python, "-c", "import pymongo"],
        capture_output=True,
        text=True,
    )
    if check.returncode != 0:
        raise RuntimeError(
            "Google Docs crawl worker is missing pymongo. "
            "Install indexer dependencies: "
            f'"{python}" -m pip install -r "{INDEXER_ROOT / "requirements.txt"}"'
        )


def start_docs_crawl(run_id: str) -> str:
    if not WORKER_SCRIPT.is_file():
        raise RuntimeError(f"Crawl worker not found: {WORKER_SCRIPT}")

    _ensure_worker_deps()

    cmd = [_worker_python(), str(WORKER_SCRIPT), run_id]
    creationflags = 0
    if os.name == "nt":
        creationflags |= BELOW_NORMAL_PRIORITY_CLASS

    with _lock:
        _cleanup_locked()
        proc = _processes.get(run_id)
        if proc is not None and proc.poll() is None:
            raise RuntimeError(f"Crawl run {run_id} is already executing")

        proc = subprocess.Popen(
            cmd,
            cwd=str(INDEXER_ROOT),
            env=_worker_env(),
            creationflags=creationflags,
        )
        _processes[run_id] = proc
        watcher = threading.Thread(
            target=_watch_worker, args=(run_id, proc), daemon=True, name=f"docs-crawl-{run_id[:8]}"
        )
        _watchers[run_id] = watcher
        watcher.start()

    log.info("Started Google Docs crawl %s in child process %s", run_id, proc.pid)
    return str(proc.pid)


def is_crawl_active(run_id: str) -> bool:
    with _lock:
        _cleanup_locked()
        proc = _processes.get(run_id)
        return proc is not None and proc.poll() is None


def has_active_crawls() -> bool:
    with _lock:
        _cleanup_locked()
        return any(proc.poll() is None for proc in _processes.values())


def terminate_crawl(run_id: str) -> None:
    with _lock:
        proc = _processes.get(run_id)
        if proc is None or proc.poll() is not None:
            _processes.pop(run_id, None)
            return
        log.warning("Terminating docs crawl process %s for run %s", proc.pid, run_id)
        proc.terminate()


def heal_run_status(run_id: str, row: dict[str, Any]) -> dict[str, Any]:
    """Mark stale running jobs as failed when the worker process is gone."""
    status = str(row.get("status") or "")
    if status not in ("pending", "running", "stopping"):
        return row
    if is_crawl_active(run_id):
        return row
    if status == "stopping":
        row = {**row, "status": "stopped"}
    elif status in ("pending", "running"):
        row = {**row, "status": "failed", "last_error": row.get("last_error") or "Worker exited unexpectedly"}
    return row
