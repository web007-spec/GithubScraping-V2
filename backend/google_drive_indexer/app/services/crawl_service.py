"""Main crawl orchestrator for public Google Drive folders."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from google_drive_db.categories import file_matches_categories
from app.crawler.downloader import download_public_file
from app.crawler.folder import probe_file_public, scan_public_folder
from app.crawler.parser import extract_text
from app.settings import Settings, get_settings
from app.utils.drive_ids import is_valid_drive_id
from app.utils.drive_urls import DriveResource, extract_resource, normalize_public_url
from app.utils.http import RateLimitedSession


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CrawlStats:
    folders_crawled: int = 0
    files_discovered: int = 0
    files_downloaded: int = 0
    files_indexed: int = 0
    failed: int = 0
    skipped_restricted: int = 0
    skipped_category: int = 0
    skipped_duplicate: int = 0
    skipped_invalid: int = 0


LogFn = Callable[[str], None]
ShouldStopFn = Callable[[], bool]


class DriveCrawlService:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        on_log: LogFn | None = None,
        should_stop: ShouldStopFn | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._on_log = on_log or (lambda _msg: None)
        self._should_stop = should_stop or (lambda: False)

    def _log(self, message: str) -> None:
        self._on_log(message)

    async def run(
        self,
        *,
        seed_urls: list[str],
        categories: list[str],
        max_depth: int = 4,
        max_files: int = 500,
    ) -> CrawlStats:
        stats = CrawlStats()
        seeds: list[DriveResource] = []
        for url in seed_urls:
            resource = extract_resource(url)
            if resource:
                seeds.append(resource)
        if not seeds:
            raise ValueError("No valid public Drive folder or file URLs provided")

        from google_drive_db import files as files_db
        from google_drive_db import folders as folders_db

        queue: deque[tuple[DriveResource, int]] = deque()
        seen_folders: set[str] = set()
        seen_files: set[str] = set()

        for seed in seeds:
            if seed.kind == "folder":
                queue.append((seed, 0))
            elif is_valid_drive_id(seed.resource_id):
                seen_files.add(seed.resource_id)
            else:
                stats.skipped_invalid += 1
                self._log(f"Skipped invalid seed URL: {seed.url}")

        async with RateLimitedSession(self.settings) as session:
            # Process direct file seeds first
            for seed in seeds:
                if seed.kind == "folder":
                    continue
                if seed.resource_id not in seen_files:
                    continue
                await self._process_file(
                    session,
                    files_db,
                    file_id=seed.resource_id,
                    name=seed.resource_id,
                    mime_type="",
                    extension="",
                    folder_id=None,
                    public_url=seed.url,
                    categories=categories,
                    stats=stats,
                    kind_hint=seed.kind,
                )
                if stats.files_indexed >= max_files or self._should_stop():
                    return stats

            while queue and stats.files_indexed < max_files:
                if self._should_stop():
                    break
                folder, depth = queue.popleft()
                if folder.resource_id in seen_folders:
                    continue
                seen_folders.add(folder.resource_id)

                scan = await scan_public_folder(session, folder, max_depth=max(0, max_depth - depth))
                stats.folders_crawled += 1
                if scan.restricted:
                    stats.skipped_restricted += 1
                    self._log(f"Skipped restricted folder {folder.resource_id}: {scan.error}")
                    continue

                folders_db.upsert_folder(
                    {
                        "folder_id": scan.folder_id,
                        "name": scan.folder_name,
                        "url": scan.folder_url,
                        "parent_folder_id": None,
                        "crawled_at": _now(),
                        "status": "crawled",
                    }
                )

                for entry in scan.files:
                    if entry.file_id in seen_files:
                        continue
                    seen_files.add(entry.file_id)
                    stats.files_discovered += 1
                    if not file_matches_categories(
                        mime_type=entry.mime_type,
                        extension=entry.extension,
                        selected=categories,
                        name=entry.name,
                    ):
                        stats.skipped_category += 1
                        continue
                    await self._process_file(
                        session,
                        files_db,
                        file_id=entry.file_id,
                        name=entry.name,
                        mime_type=entry.mime_type,
                        extension=entry.extension,
                        folder_id=entry.folder_id,
                        public_url=entry.public_url,
                        categories=categories,
                        stats=stats,
                        kind_hint=entry.kind,
                    )
                    if stats.files_indexed >= max_files or self._should_stop():
                        break

                if depth < max_depth:
                    for sub_id in scan.subfolders:
                        if sub_id not in seen_folders:
                            queue.append(
                                (
                                    DriveResource(
                                        kind="folder",
                                        resource_id=sub_id,
                                        url=normalize_public_url("folder", sub_id),
                                    ),
                                    depth + 1,
                                )
                            )

        return stats

    async def _process_file(
        self,
        session: RateLimitedSession,
        files_db: Any,
        *,
        file_id: str,
        name: str,
        mime_type: str,
        extension: str,
        folder_id: str | None,
        public_url: str,
        categories: list[str],
        stats: CrawlStats,
        kind_hint: str = "file",
    ) -> None:
        if not is_valid_drive_id(file_id):
            stats.skipped_invalid += 1
            return

        if files_db.find_by_file_id(file_id):
            stats.skipped_duplicate += 1
            return

        is_public, err = await probe_file_public(session, file_id)
        if not is_public:
            stats.skipped_restricted += 1
            self._log(f"Skipped non-public file {file_id}: {err}")
            return

        dl = await download_public_file(
            session,
            self.settings,
            file_id=file_id,
            mime_type=mime_type,
            suggested_name=name or file_id,
            kind_hint=kind_hint,
        )
        if not dl.ok or not dl.path:
            stats.failed += 1
            files_db.upsert_file(
                {
                    "file_id": file_id,
                    "name": name,
                    "mime_type": dl.mime_type or mime_type,
                    "extension": extension,
                    "folder_id": folder_id,
                    "public_url": public_url,
                    "status": "failed",
                    "error": dl.error,
                    "categories": categories,
                }
            )
            self._log(f"Failed {name or file_id}: {dl.error}")
            return

        stats.files_downloaded += 1
        resolved_ext = extension or (dl.path.suffix.lstrip(".") if dl.path.suffix else "")
        category_mime = dl.mime_type or mime_type
        if dl.strategy:
            if "document" in dl.strategy:
                category_mime = "application/vnd.google-apps.document"
            elif "spreadsheet" in dl.strategy:
                category_mime = "application/vnd.google-apps.spreadsheet"
            elif "presentation" in dl.strategy:
                category_mime = "application/vnd.google-apps.presentation"
        if not file_matches_categories(
            mime_type=category_mime,
            extension=resolved_ext,
            selected=categories,
            name=name,
        ):
            stats.skipped_category += 1
            dl.path.unlink(missing_ok=True)
            self._log(f"Skipped {name or file_id} — does not match selected categories")
            return

        extracted = extract_text(dl.path, dl.mime_type)
        if files_db.find_by_hash(dl.sha256):
            stats.skipped_duplicate += 1
            dl.path.unlink(missing_ok=True)
            return

        files_db.upsert_file(
            {
                "file_id": file_id,
                "folder_id": folder_id,
                "name": name,
                "mime_type": dl.mime_type,
                "extension": resolved_ext,
                "size": dl.size,
                "sha256": dl.sha256,
                "md5": dl.md5,
                "public_url": public_url,
                "download_path": str(dl.path),
                "raw_text": extracted.raw_text,
                "word_count": extracted.word_count,
                "page_count": extracted.page_count,
                "language": extracted.language,
                "categories": categories,
                "status": "indexed",
                "indexed_at": _now(),
            }
        )
        stats.files_indexed += 1
        self._log(f"Indexed {name or file_id} via {dl.strategy or 'download'} ({dl.size:,} bytes)")
