"""Batch web search for discovering thousands of Google Docs URLs."""

import asyncio
from pathlib import Path

from loguru import logger

from app.config.settings import Settings, get_settings
from app.crawler.search_backends import search_all_backends
from app.utils.url_utils import extract_google_doc_id, normalize_google_docs_url


class BatchSearchService:
    """
    Run many search queries concurrently to discover large volumes of docs.

    Each query returns ~25-100 URLs. With 400+ queries you can reach 10k+ unique docs.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def discover(
        self,
        queries: list[str],
        target: int = 1000,
        results_per_query: int = 50,
        output: Path | None = None,
        resume: bool = True,
    ) -> list[tuple[str, str]]:
        """
        Run batch search and return (doc_id, url) tuples.

        Incrementally saves to output file when provided.
        """
        output = output or self._settings.data_dir / "discovered_urls.txt"
        seen_ids = self._load_existing_ids(output) if resume else set()
        discovered: list[tuple[str, str]] = []
        initial_count = len(seen_ids)

        if initial_count >= target:
            logger.info(
                "Catalog already has {} URLs (goal {}). Skipping batch search queries.",
                initial_count,
                target,
            )
            return discovered

        if seen_ids:
            logger.info(
                "Resuming with {} URLs in {}; discovering up to {} total",
                len(seen_ids),
                output,
                target,
            )

        semaphore = asyncio.Semaphore(self._settings.search_concurrency)
        lock = asyncio.Lock()
        query_count = 0

        async def run_query(raw_query: str) -> None:
            nonlocal query_count
            async with semaphore:
                if len(seen_ids) >= target:
                    return

                query = raw_query.strip()
                if not query:
                    return

                if "site:docs.google.com" not in query:
                    query = f"site:docs.google.com/document {query}"

                urls = await search_all_backends(
                    query,
                    max_results=results_per_query,
                    settings=self._settings,
                )

                new_urls: list[str] = []
                async with lock:
                    for url in urls:
                        if len(seen_ids) >= target:
                            break
                        normalized = normalize_google_docs_url(url)
                        if not normalized:
                            continue
                        doc_id = extract_google_doc_id(normalized)
                        if not doc_id or doc_id in seen_ids:
                            continue
                        seen_ids.add(doc_id)
                        discovered.append((doc_id, normalized))
                        new_urls.append(normalized)

                    query_count += 1
                    if new_urls:
                        self._append_urls(output, new_urls)
                        logger.info(
                            "Query {} (+{} new, total {}/{}): {}",
                            query_count,
                            len(new_urls),
                            len(seen_ids),
                            target,
                            raw_query[:50],
                        )
                    else:
                        logger.debug("Query {} (0 new): {}", query_count, raw_query[:50])

        tasks = [run_query(q) for q in queries]
        await asyncio.gather(*tasks)

        logger.info(
            "Batch search complete: {} new URLs this run ({} total in catalog, goal {})",
            len(discovered),
            len(seen_ids),
            target,
        )
        return discovered

    @staticmethod
    def load_queries(path: Path) -> list[str]:
        """Load search queries from a text file."""
        if not path.exists():
            logger.warning("Query file not found: {}", path)
            return []
        queries: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                queries.append(line)
        logger.info("Loaded {} search queries from {}", len(queries), path)
        return queries

    @staticmethod
    def generate_queries(keywords: list[str], suffixes: list[str] | None = None) -> list[str]:
        """Generate query combinations from keywords and suffixes."""
        suffixes = suffixes or [
            "template", "example", "sample", "format", "guide",
            "document", "form", "report", "plan", "checklist",
        ]
        queries: list[str] = []
        for kw in keywords:
            queries.append(kw)
            for suffix in suffixes:
                queries.append(f"{kw} {suffix}")
        return queries

    @staticmethod
    def _load_existing_ids(path: Path) -> set[str]:
        ids: set[str] = set()
        if not path.exists():
            return ids
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            doc_id = extract_google_doc_id(line)
            if doc_id:
                ids.add(doc_id)
        return ids

    @staticmethod
    def _append_urls(path: Path, urls: list[str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            for url in urls:
                f.write(url + "\n")
