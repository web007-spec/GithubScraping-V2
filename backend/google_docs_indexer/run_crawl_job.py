"""Subprocess worker: discover + crawl Google Docs, persist to database."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config.settings import get_settings
from app.services.batch_search_service import BatchSearchService
from app.services.csv_crawl_service import CrawlStats, CsvCrawlService
from app.services.document_store import is_db_storage_enabled, require_db_storage
from app.utils.csv_writer import CsvRow


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _use_mongo() -> bool:
    mode = (
        os.environ.get("DATABASE_STORAGE")
        or os.environ.get("GOOGLE_DOCS_STORAGE")
        or "auto"
    ).strip().lower()
    uri = (os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI") or "").strip()
    if mode == "supabase":
        return False
    if mode == "mongodb":
        return bool(uri)
    return bool(uri)


def _fetch_run(run_id: str) -> dict:
    if _use_mongo():
        from google_docs_db import crawl_runs

        row = crawl_runs.fetch_run(run_id)
    else:
        from supabase import create_client

        url = os.environ.get("SUPABASE_URL", "").strip()
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        result = (
            create_client(url, key)
            .table("google_docs_crawl_runs")
            .select("*")
            .eq("id", run_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        row = rows[0] if rows else None
    if not row:
        raise RuntimeError(f"Crawl run not found: {run_id}")
    return row


def _append_log(run_id: str, message: str) -> None:
    if _use_mongo():
        from google_docs_db import crawl_runs

        crawl_runs.append_log(run_id, message)
        return
    row = _fetch_run(run_id)
    lines = list(row.get("log_lines") or [])
    lines.append({"ts": _now_iso(), "message": message})
    if len(lines) > 200:
        lines = lines[-200:]
    _update_run(run_id, log_lines=lines)


def _update_run(run_id: str, **fields) -> None:
    if _use_mongo():
        from google_docs_db import crawl_runs

        crawl_runs.update_run(run_id, fields)
        return
    from supabase import create_client

    fields["updated_at"] = _now_iso()
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    create_client(url, key).table("google_docs_crawl_runs").update(fields).eq("id", run_id).execute()


def _run_status(run_id: str) -> str:
    return str(_fetch_run(run_id).get("status") or "")


def _should_stop(run_id: str) -> bool:
    return _run_status(run_id) in ("stopping", "stopped")


def _progress_loop(run_id: str, stats: CrawlStats, stop_event: threading.Event) -> None:
    while not stop_event.wait(5.0):
        if _should_stop(run_id):
            return
        try:
            _update_run(
                run_id,
                crawled_count=stats.crawled,
                parsed_count=stats.parsed,
                failed_count=stats.failed,
                current_phase="crawling",
            )
        except Exception:
            pass


async def _execute_crawl(run_id: str, config: dict, stats: CrawlStats) -> CrawlStats:
    settings = get_settings()
    workers = int(config.get("workers") or settings.max_workers)
    settings.max_workers = max(1, min(workers, 100))

    resume = bool(config.get("resume", True))
    mode = str(config.get("mode") or "search")

    def on_progress(_row: CsvRow) -> None:
        _update_run(
            run_id,
            crawled_count=stats.crawled,
            parsed_count=stats.parsed,
            failed_count=stats.failed,
            current_phase="crawling",
        )

    service = CsvCrawlService(settings, on_progress=on_progress)

    if mode == "batch_search":
        queries_file = config.get("queries_file")
        qpath = Path(queries_file) if queries_file else settings.queries_file
        queries = BatchSearchService.load_queries(qpath)
        if not queries:
            raise RuntimeError(f"No queries in {qpath}")
        target = int(config.get("target") or 10_000)
        max_results = int(config.get("max_results") or settings.search_max_results)
        _update_run(run_id, current_phase="discovering", discovered_count=0)
        _append_log(run_id, f"Batch search: {len(queries)} queries, goal {target:,}, {max_results} per query")
        if _should_stop(run_id):
            raise RuntimeError("Stopped before crawl")
        return await service.crawl_from_batch_search(
            queries,
            target=target,
            resume=resume,
            results_per_query=max_results,
        )

    if mode == "from_discovered":
        discovered_file = config.get("url_file")
        path = Path(discovered_file) if discovered_file else settings.discovered_urls_file
        _append_log(run_id, f"Crawling discovered URLs from {path}")
        return await service.crawl_from_discovered(path, resume=resume)

    if mode == "from_file":
        url_file = config.get("url_file") or settings.url_list_file
        path = Path(url_file)
        _append_log(run_id, f"Crawling URL list from {path}")
        return await service.crawl_from_file(path, resume=resume)

    query = str(config.get("query") or "").strip()
    if not query:
        raise RuntimeError("Search query is required for search mode")
    max_results = int(config.get("max_results") or settings.search_max_results)
    discovery_target = int(config.get("target") or 10_000)
    _update_run(run_id, current_phase="discovering")
    _append_log(run_id, f"Searching: {query} (discovery goal {discovery_target:,})")
    return await service.crawl_from_search(
        query,
        max_results=max_results,
        resume=resume,
        discovery_target=discovery_target,
    )


async def run_job(run_id: str) -> None:
    require_db_storage()
    run = _fetch_run(run_id)
    config = run.get("config") or {}
    if isinstance(config, str):
        config = json.loads(config)

    stats = CrawlStats()
    stop_event = threading.Event()
    progress_thread = threading.Thread(
        target=_progress_loop, args=(run_id, stats, stop_event), daemon=True
    )
    db_label = "MongoDB" if _use_mongo() else "Supabase"

    try:
        _update_run(run_id, status="running", started_at=_now_iso(), current_phase="starting")
        _append_log(run_id, f"Crawl worker started ({db_label})")
        progress_thread.start()

        crawl_stats = await _execute_crawl(run_id, config, stats)
        stats = crawl_stats

        if _should_stop(run_id):
            _update_run(
                run_id,
                status="stopped",
                ended_at=_now_iso(),
                current_phase="stopped",
                crawled_count=stats.crawled,
                parsed_count=stats.parsed,
                failed_count=stats.failed,
            )
            _append_log(run_id, "Crawl stopped by user")
            return

        discovered_path = get_settings().discovered_urls_file
        discovered_count = len(BatchSearchService._load_existing_ids(discovered_path))

        imported = stats.parsed if config.get("auto_import", True) else 0
        _update_run(
            run_id,
            discovered_count=discovered_count,
            crawled_count=stats.crawled,
            parsed_count=stats.parsed,
            failed_count=stats.failed,
            imported_count=imported,
            current_phase="completed",
            status="completed",
            ended_at=_now_iso(),
        )
        finish_msg = f"Crawl finished: {stats.parsed} saved to {db_label}, {stats.failed} failed"
        if stats.crawled == 0:
            finish_msg += " — no new documents (catalog may already be crawled; raise discovery goal or use batch search)"
        _append_log(run_id, finish_msg)
        _append_log(run_id, "Job completed successfully")
    except Exception as exc:
        _update_run(
            run_id,
            status="failed",
            ended_at=_now_iso(),
            last_error=str(exc),
            current_phase="failed",
            crawled_count=stats.crawled,
            parsed_count=stats.parsed,
            failed_count=stats.failed,
        )
        _append_log(run_id, f"Job failed: {exc}")
        raise
    finally:
        stop_event.set()
        progress_thread.join(timeout=2.0)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python run_crawl_job.py <run_id>", file=sys.stderr)
        sys.exit(2)
    run_id = sys.argv[1]
    asyncio.run(run_job(run_id))


if __name__ == "__main__":
    main()
