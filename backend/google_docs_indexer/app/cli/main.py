"""Typer CLI entry point."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

from app import __version__
from app.config.settings import get_settings
from app.database.engine import async_session_factory, create_engine
from app.parser.cleaner import clean_text
from app.services.batch_search_service import BatchSearchService
from app.services.crawl_service import CrawlService
from app.services.csv_crawl_service import CrawlStats, CsvCrawlService
from app.services.discovery_service import run_discovery
from app.services.document_store import is_db_storage_enabled, require_db_storage
from app.services.mongo_discovery_service import run_discovery_db
from app.services.export_service import ExportService
from app.services.search_service import SearchService
from app.services.stats_service import StatsService
from app.utils.csv_writer import read_csv_rows
from app.utils.logging import setup_logging

app = typer.Typer(
    name="google-docs-indexer",
    help="Discover, download, and index publicly accessible Google Docs.",
    no_args_is_help=True,
)
console = Console()


def _run_async(coro):
    return asyncio.run(coro)


@app.callback()
def main() -> None:
    """Initialize logging on every command."""
    setup_logging()


@app.command()
def discover(
    url_file: Optional[Path] = typer.Option(
        None, "--file", "-f", help="Path to URL list file (default: data/discovered_urls.txt)"
    ),
) -> None:
    """Discover Google Docs URLs and register them in the database."""
    settings = get_settings()
    path = url_file or settings.discovered_urls_file

    if is_db_storage_enabled():
        async def _discover_db():
            return await run_discovery_db(settings, path)

        registered, total = _run_async(_discover_db())
        console.print(
            f"[green]Loaded {total} URLs from {path}, registered {registered} in database[/green]"
        )
        return

    create_engine(settings)

    async def _discover():
        factory = async_session_factory()
        async with factory() as session:
            count = await run_discovery(session, settings, url_file=str(path))
            return count

    count = _run_async(_discover())
    console.print(f"[green]Discovered {count} new documents in Postgres[/green]")


@app.command("crawl-csv")
def crawl_csv(
    url_file: Optional[Path] = typer.Option(
        None, "--file", "-f", help="Path to URL list file"
    ),
    workers: Optional[int] = typer.Option(
        None, "--workers", "-w", help="Number of concurrent workers (default 50)"
    ),
    demo: bool = typer.Option(
        False, "--demo", help="Run with sample data (no network, for initial testing)"
    ),
    search: Optional[str] = typer.Option(
        None, "--search", "-s", help="Single search query for public Google Docs"
    ),
    batch_search: bool = typer.Option(
        False, "--batch-search", help="Run many queries from queries file"
    ),
    from_discovered: bool = typer.Option(
        False, "--from-discovered", help="Crawl URLs from data/discovered_urls.txt (default when no search)"
    ),
    queries_file: Optional[Path] = typer.Option(
        None, "--queries", "-q", help="Query list file for --batch-search"
    ),
    target: int = typer.Option(
        10_000, "--target", "-t", help="Discovery goal: total unique URLs in catalog"
    ),
    max_results: int = typer.Option(
        50, "--max-results", "-n", help="Max docs per search query"
    ),
    resume: bool = typer.Option(
        True, "--resume/--no-resume", help="Skip documents already stored in the database"
    ),
) -> None:
    """Crawl public Google Docs and save results to the database."""
    settings = get_settings()
    if workers:
        settings.max_workers = workers

    if demo:
        console.print("[yellow]Demo mode writes sample rows only when database storage is configured.[/yellow]")
        require_db_storage()
        from app.utils.csv_writer import CsvRow
        from app.services.document_store import persist_row
        from app.utils.hashing import compute_sha256

        sample_text = "Hello World\n\nThis is a sample public document for testing."
        persist_row(
            CsvRow(
                google_doc_id="demo_doc_001",
                url="https://docs.google.com/document/d/demo_doc_001/edit",
                title="Sample Public Document",
                clean_text=sample_text,
                headings="Introduction | Summary",
                word_count=len(sample_text.split()),
                character_count=len(sample_text),
                language="en",
                sha256=compute_sha256(sample_text),
                links_count=2,
                images_count=1,
                status="parsed",
                elapsed_ms=842,
            )
        )
        console.print("[green]Saved demo document to database[/green]")
        return

    require_db_storage()

    use_discovered = from_discovered or (
        not search and not batch_search and settings.discovered_urls_file.exists()
    )

    if batch_search:
        qfile = queries_file or settings.queries_file
        queries = BatchSearchService.load_queries(qfile)
        if not queries:
            console.print(f"[red]No queries in {qfile}. Add search terms (one per line).[/red]")
            raise typer.Exit(1)

        async def _batch():
            service = CsvCrawlService(settings)
            return await service.crawl_from_batch_search(
                queries,
                target=target,
                resume=resume,
                results_per_query=max_results,
            )

        stats = _run_async(_batch())
        discovered_count = len(BatchSearchService._load_existing_ids(settings.discovered_urls_file))
        console.print(f"[dim]{discovered_count} URLs in {settings.discovered_urls_file}[/dim]")
    elif use_discovered:
        discovered_file = url_file or settings.discovered_urls_file

        async def _from_disc():
            service = CsvCrawlService(settings)
            return await service.crawl_from_discovered(discovered_file, resume=resume)

        stats = _run_async(_from_disc())
    elif search:
        async def _search_crawl():
            service = CsvCrawlService(settings)
            return await service.crawl_from_search(
                search,
                max_results=max_results,
                resume=resume,
            )

        stats = _run_async(_search_crawl())
        console.print(f"[dim]Discovered URLs saved to {settings.discovered_urls_file}[/dim]")
    else:
        input_file = url_file or settings.url_list_file

        async def _crawl():
            service = CsvCrawlService(settings)
            return await service.crawl_from_file(input_file, resume=resume)

        stats = _run_async(_crawl())

    _print_crawl_summary(stats)


def _print_crawl_summary(stats: CrawlStats) -> None:
    table = Table(title="Crawl results (database)")
    table.add_column("Metric", style="cyan")
    table.add_column("Count")

    table.add_row("Crawled", str(stats.crawled))
    table.add_row("Parsed (saved)", str(stats.parsed))
    table.add_row("Failed", str(stats.failed))
    table.add_row("Duplicate", str(stats.duplicate))
    table.add_row("Skipped", str(stats.skipped))

    console.print(table)
    console.print(
        f"[green]Saved {stats.parsed} documents to the database "
        f"({stats.failed} failed)[/green]"
    )


@app.command("import-legacy-csv")
def import_legacy_csv(
    csv_path: Path = typer.Option(
        Path("data/results.csv"), "--file", "-f", help="Legacy CSV file to import"
    ),
    only_parsed: bool = typer.Option(True, "--only-parsed/--all", help="Import only parsed rows"),
) -> None:
    """One-time import from legacy results.csv into the database."""
    require_db_storage()
    from app.services.document_store import persist_row
    from app.utils.csv_writer import CsvRow

    if not csv_path.is_file():
        console.print(f"[red]File not found: {csv_path}[/red]")
        raise typer.Exit(1)

    imported = 0
    for record in read_csv_rows(csv_path):
        status = str(record.get("status") or "").strip().lower()
        if only_parsed and status != "parsed":
            continue
        row = CsvRow(
            google_doc_id=str(record.get("google_doc_id") or ""),
            url=str(record.get("url") or ""),
            title=record.get("title"),
            excerpt=record.get("excerpt"),
            clean_text=record.get("clean_text"),
            search_text=record.get("search_text"),
            headings=record.get("headings"),
            word_count=int(record["word_count"]) if record.get("word_count") else None,
            character_count=int(record["character_count"]) if record.get("character_count") else None,
            language=record.get("language"),
            sha256=record.get("sha256"),
            preview_url=record.get("preview_url"),
            preview_image_url=record.get("preview_image_url"),
            images_count=int(record.get("images_count") or 0),
            archive_json=record.get("archive_json"),
            shared_by_email=record.get("shared_by_email"),
            shared_by_name=record.get("shared_by_name"),
            shared_at=record.get("shared_at"),
            document_modified_at=record.get("document_modified_at"),
            status=status or "parsed",
            error=record.get("error"),
            crawled_at=record.get("crawled_at") or "",
        )
        persist_row(row)
        imported += 1

    console.print(f"[green]Imported {imported} rows from {csv_path} into the database[/green]")


@app.command("enrich-metadata")
def enrich_metadata(
    limit: int = typer.Option(0, "--limit", "-n", help="Max documents to process (0 = all)"),
    force: bool = typer.Option(
        False, "--force", help="Re-extract even when a non-placeholder email exists"
    ),
    workers: int = typer.Option(8, "--workers", "-w", help="Parallel metadata fetch workers"),
) -> None:
    """Backfill shared_by_email and sharing dates for archived documents."""
    require_db_storage()
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from app.parser.metadata_extractor import fetch_document_metadata_sync, is_placeholder_email
    from google_docs_db.client import get_database

    db = get_database()
    query: dict = {"status": "parsed"}
    if not force:
        query["$or"] = [
            {"shared_by_email": None},
            {"shared_by_email": ""},
            {"shared_by_email": {"$regex": r"@example\.com$", "$options": "i"}},
            {"shared_by_email": {"$regex": r"no.?reply", "$options": "i"}},
        ]
    cursor = db.google_documents.find(query, {"google_doc_id": 1, "shared_by_email": 1, "clean_text": 1})
    if limit > 0:
        cursor = cursor.limit(limit)
    docs = list(cursor)
    if not docs:
        console.print("[green]No documents need metadata enrichment.[/green]")
        return

    console.print(f"[cyan]Enriching metadata for {len(docs)} documents…[/cyan]")
    updated = 0

    def _enrich_one(doc: dict) -> tuple[str, dict | None]:
        doc_id = str(doc.get("google_doc_id") or "").strip()
        if not doc_id:
            return "", None
        meta = fetch_document_metadata_sync(doc_id)
        clean_text = str(doc.get("clean_text") or "")
        if clean_text:
            from app.parser.metadata_extractor import extract_document_metadata

            content_meta = extract_document_metadata(clean_text=clean_text)
            if content_meta.shared_by_email and (
                not meta.shared_by_email
                or is_placeholder_email(meta.shared_by_email)
            ):
                meta.shared_by_email = content_meta.shared_by_email
            if content_meta.shared_by_name and not meta.shared_by_name:
                meta.shared_by_name = content_meta.shared_by_name
        if not meta.shared_by_email:
            if doc.get("shared_by_email") and is_placeholder_email(doc.get("shared_by_email")):
                return doc_id, {"shared_by_email": None, "shared_by_name": None}
            return doc_id, None
        if not force and doc.get("shared_by_email") and not is_placeholder_email(doc.get("shared_by_email")):
            return doc_id, None
        patch: dict = {"shared_by_email": meta.shared_by_email}
        if meta.shared_by_name:
            patch["shared_by_name"] = meta.shared_by_name
        if meta.shared_at:
            patch["shared_at"] = meta.shared_at
        if meta.document_modified_at:
            patch["document_modified_at"] = meta.document_modified_at
        return doc_id, patch

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_enrich_one, doc) for doc in docs]
        for future in as_completed(futures):
            doc_id, patch = future.result()
            if not doc_id or not patch:
                continue
            db.google_documents.update_one({"google_doc_id": doc_id}, {"$set": patch})
            updated += 1

    console.print(f"[green]Updated {updated} documents with contact/sharing email metadata[/green]")


@app.command()
def crawl(
    workers: Optional[int] = typer.Option(None, "--workers", "-w", help="Number of workers"),
    limit: int = typer.Option(10000, "--limit", "-l", help="Max documents to queue"),
) -> None:
    """Crawl and index queued documents."""
    settings = get_settings()
    if workers:
        settings.max_workers = workers
    create_engine(settings)

    async def _crawl():
        factory = async_session_factory()
        service = CrawlService(factory, settings)
        queued = await service.load_pending_into_queue(limit=limit)
        if queued == 0:
            logger.info("No pending documents to crawl")
            return
        stats = await service.run()
        return stats

    stats = _run_async(_crawl())
    if stats:
        console.print(
            f"[green]Crawl complete: {stats.downloaded} downloaded, "
            f"{stats.failed} failed, {stats.duplicates} duplicates[/green]"
        )


@app.command()
def resume(
    workers: Optional[int] = typer.Option(None, "--workers", "-w"),
    limit: int = typer.Option(10000, "--limit", "-l"),
) -> None:
    """Resume interrupted crawl from pending documents."""
    settings = get_settings()
    if workers:
        settings.max_workers = workers
    create_engine(settings)

    async def _resume():
        factory = async_session_factory()
        service = CrawlService(factory, settings)
        queued = await service.load_pending_into_queue(limit=limit)
        console.print(f"Resuming with {queued} documents in queue")
        return await service.run()

    stats = _run_async(_resume())
    if stats:
        console.print(f"[green]Resumed crawl: {stats.downloaded} downloaded[/green]")


@app.command()
def retry(
    limit: int = typer.Option(1000, "--limit", "-l"),
    workers: Optional[int] = typer.Option(None, "--workers", "-w"),
) -> None:
    """Retry failed document downloads."""
    settings = get_settings()
    if workers:
        settings.max_workers = workers
    create_engine(settings)

    async def _retry():
        factory = async_session_factory()
        service = CrawlService(factory, settings)
        queued = await service.load_failed_into_queue(limit=limit)
        if queued == 0:
            console.print("[yellow]No failed documents to retry[/yellow]")
            return None
        return await service.run()

    stats = _run_async(_retry())
    if stats:
        console.print(f"[green]Retry complete: {stats.downloaded} recovered[/green]")


@app.command()
def stats() -> None:
    """Display crawl statistics dashboard."""
    settings = get_settings()
    create_engine(settings)

    async def _stats():
        factory = async_session_factory()
        async with factory() as session:
            service = StatsService(session, settings)
            dashboard = await service.get_dashboard()
            return service.format_dashboard(dashboard)

    console.print(_run_async(_stats()))


@app.command()
def search(
    query: Optional[str] = typer.Option(None, "--query", "-q"),
    title: Optional[str] = typer.Option(None, "--title", "-t"),
    language: Optional[str] = typer.Option(None, "--lang"),
    date_from: Optional[str] = typer.Option(None, "--from"),
    date_to: Optional[str] = typer.Option(None, "--to"),
    full_text: bool = typer.Option(False, "--full-text", "-f"),
    limit: int = typer.Option(20, "--limit", "-l"),
) -> None:
    """Search indexed documents."""
    settings = get_settings()
    create_engine(settings)

    df = datetime.fromisoformat(date_from) if date_from else None
    dt = datetime.fromisoformat(date_to) if date_to else None

    async def _search():
        factory = async_session_factory()
        async with factory() as session:
            service = SearchService(session)
            return await service.search(
                query=query,
                title=title,
                language=language,
                date_from=df,
                date_to=dt,
                full_text=full_text,
                limit=limit,
            )

    results = _run_async(_search())
    table = Table(title="Search Results")
    table.add_column("Title", style="cyan")
    table.add_column("Language")
    table.add_column("Words")
    table.add_column("URL")

    for doc in results:
        table.add_row(
            (doc.title or "Untitled")[:60],
            doc.language or "-",
            str(doc.word_count or 0),
            doc.url[:50] + "..." if len(doc.url) > 50 else doc.url,
        )
    console.print(table)
    console.print(f"[dim]{len(results)} results[/dim]")


@app.command()
def export(
    output: Path = typer.Option(Path("data/export.json"), "--output", "-o"),
    format: str = typer.Option("json", "--format", "-f", help="json, csv, or markdown"),
    limit: Optional[int] = typer.Option(None, "--limit", "-l"),
) -> None:
    """Export indexed documents."""
    settings = get_settings()
    create_engine(settings)

    async def _export():
        factory = async_session_factory()
        async with factory() as session:
            service = ExportService(session)
            return await service.export(output, fmt=format, limit=limit)

    count = _run_async(_export())
    console.print(f"[green]Exported {count} documents to {output}[/green]")


@app.command()
def clean(
    text: str = typer.Argument(..., help="Text to clean"),
) -> None:
    """Clean text using the indexer cleaner pipeline."""
    result = clean_text(text)
    console.print(result)


@app.command()
def version() -> None:
    """Show version."""
    console.print(f"Google Docs Public Indexer v{__version__}")


def cli_main() -> None:
    app()


if __name__ == "__main__":
    cli_main()
