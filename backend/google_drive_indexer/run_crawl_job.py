"""Subprocess worker: discover public Drive URLs + crawl folders → MongoDB."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _use_mongo() -> bool:
    uri = (os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI") or "").strip()
    mode = (os.environ.get("DATABASE_STORAGE") or "mongodb").strip().lower()
    if mode == "supabase":
        return False
    return bool(uri)


def _fetch_run(run_id: str) -> dict:
    from google_drive_db import crawl_runs

    row = crawl_runs.fetch_run(run_id)
    if not row:
        raise RuntimeError(f"Crawl run not found: {run_id}")
    return row


def _update_run(run_id: str, **fields) -> None:
    from google_drive_db import crawl_runs

    crawl_runs.update_run(run_id, fields)


def _append_log(run_id: str, message: str) -> None:
    from google_drive_db import crawl_runs

    crawl_runs.append_log(run_id, message)


def _should_stop(run_id: str) -> bool:
    status = str(_fetch_run(run_id).get("status") or "")
    return status in ("stopping", "stopped")


async def _resolve_seed_urls(run_id: str, config: dict) -> list[str]:
    from app.services.batch_search_service import BatchSearchService
    from app.services.query_builder import merge_query_sources
    from app.settings import get_settings

    settings = get_settings()
    mode = str(config.get("mode") or "batch_search")
    categories = list(config.get("categories") or [])
    resume = bool(config.get("resume", True))

    def on_discovered(count: int) -> None:
        _update_run(run_id, discovered_count=count, current_phase="discovering")

    if mode == "folder_crawl":
        return list(config.get("seed_urls") or [])

    if mode == "from_discovered":
        discovered_file = config.get("url_file")
        path = Path(discovered_file) if discovered_file else settings.discovered_urls_file
        urls = BatchSearchService._load_urls(path)
        _append_log(run_id, f"Loaded {len(urls)} URLs from {path}")
        _update_run(run_id, discovered_count=len(urls))
        return urls

    batch = BatchSearchService(settings)

    if mode == "batch_search":
        queries_file = config.get("queries_file")
        qpath = Path(queries_file) if queries_file else settings.queries_file
        queries = merge_query_sources(categories=categories, queries_file=qpath)
        if not queries:
            raise RuntimeError(f"No search queries for categories in {qpath}")
        target = int(config.get("target") or 500)
        max_results = int(config.get("max_results") or settings.search_max_results)
        _append_log(
            run_id,
            f"Batch search: {len(queries)} queries, goal {target:,}, {max_results} per query",
        )
        return await batch.discover(
            queries,
            target=target,
            results_per_query=max_results,
            resume=resume,
            on_progress=on_discovered,
        )

    query = str(config.get("query") or "").strip()
    if not query:
        raise RuntimeError("Search query is required for search mode")
    max_results = int(config.get("max_results") or settings.search_max_results)
    target = int(config.get("target") or 500)
    _append_log(run_id, f"Searching: {query} (discovery goal {target:,})")
    return await batch.discover(
        [query],
        target=target,
        results_per_query=max_results,
        resume=resume,
        on_progress=on_discovered,
    )


async def run_job(run_id: str) -> None:
    if not _use_mongo():
        raise RuntimeError("Google Drive indexer requires MongoDB (MONGODB_URI)")

    run = _fetch_run(run_id)
    config = run.get("config") or {}
    if isinstance(config, str):
        config = json.loads(config)

    categories = list(config.get("categories") or [])
    max_depth = int(config.get("max_depth") or 4)
    max_files = int(config.get("max_files") or 500)

    from app.services.crawl_service import CrawlStats, DriveCrawlService
    from app.settings import get_settings

    settings = get_settings()
    workers = int(config.get("workers") or settings.workers)
    settings.workers = max(1, min(workers, 32))

    stats = CrawlStats()

    def on_log(message: str) -> None:
        _append_log(run_id, message)
        _update_run(
            run_id,
            folders_crawled=stats.folders_crawled,
            files_discovered=stats.files_discovered,
            files_downloaded=stats.files_downloaded,
            files_indexed=stats.files_indexed,
            failed_count=stats.failed,
            current_phase="crawling",
        )

    service = DriveCrawlService(settings, on_log=on_log, should_stop=lambda: _should_stop(run_id))

    try:
        _update_run(run_id, status="running", started_at=_now(), current_phase="starting")
        _append_log(
            run_id,
            f"Drive crawl started — mode {config.get('mode', 'batch_search')}, "
            f"categories: {', '.join(categories) or 'all'}",
        )

        if _should_stop(run_id):
            raise RuntimeError("Stopped before crawl")

        _update_run(run_id, current_phase="discovering")
        seed_urls = await _resolve_seed_urls(run_id, config)
        if not seed_urls:
            raise RuntimeError(
                "No public Drive URLs discovered. Try a higher discovery goal, different categories, "
                "or run batch search first to populate discovered_urls.txt."
            )

        _append_log(run_id, f"Discovery complete — {len(seed_urls)} seed URLs")
        _update_run(run_id, discovered_count=len(seed_urls), current_phase="crawling")

        if _should_stop(run_id):
            raise RuntimeError("Stopped before crawl")

        stats = await service.run(
            seed_urls=seed_urls,
            categories=categories,
            max_depth=max_depth,
            max_files=max_files,
        )

        if _should_stop(run_id):
            _update_run(
                run_id,
                status="stopped",
                ended_at=_now(),
                current_phase="stopped",
                folders_crawled=stats.folders_crawled,
                files_discovered=stats.files_discovered,
                files_downloaded=stats.files_downloaded,
                files_indexed=stats.files_indexed,
                failed_count=stats.failed,
            )
            _append_log(run_id, "Crawl stopped by user")
            return

        _update_run(
            run_id,
            status="completed",
            ended_at=_now(),
            current_phase="completed",
            folders_crawled=stats.folders_crawled,
            files_discovered=stats.files_discovered,
            files_downloaded=stats.files_downloaded,
            files_indexed=stats.files_indexed,
            failed_count=stats.failed,
        )
        _append_log(
            run_id,
            f"Completed: {stats.files_indexed} indexed, {stats.failed} failed, "
            f"{stats.skipped_restricted} restricted, {stats.skipped_category} filtered by category",
        )
    except Exception as exc:
        _update_run(
            run_id,
            status="failed",
            ended_at=_now(),
            last_error=str(exc),
            current_phase="failed",
            folders_crawled=stats.folders_crawled,
            files_discovered=stats.files_discovered,
            files_downloaded=stats.files_downloaded,
            files_indexed=stats.files_indexed,
            failed_count=stats.failed,
        )
        _append_log(run_id, f"Job failed: {exc}")
        raise


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python run_crawl_job.py <run_id>", file=sys.stderr)
        sys.exit(2)
    asyncio.run(run_job(sys.argv[1]))


if __name__ == "__main__":
    main()
