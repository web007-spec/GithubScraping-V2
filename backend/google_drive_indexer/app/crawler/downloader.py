"""Download public Drive files with multi-strategy export + fallback."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.crawler.public_content import fetch_public_content, write_fetched_bytes
from app.settings import Settings
from app.utils.drive_urls import DriveResourceKind
from app.utils.hashing import md5_bytes, sha256_bytes
from app.utils.http import RateLimitedSession


@dataclass
class DownloadResult:
    ok: bool
    path: Path | None
    size: int
    sha256: str
    md5: str
    mime_type: str
    error: str | None = None
    strategy: str | None = None


async def download_public_file(
    session: RateLimitedSession,
    settings: Settings,
    *,
    file_id: str,
    mime_type: str,
    suggested_name: str,
    kind_hint: DriveResourceKind | str = "file",
) -> DownloadResult:
    fetched = await fetch_public_content(
        session,
        settings,
        file_id=file_id,
        mime_type=mime_type,
        suggested_name=suggested_name,
        kind_hint=kind_hint,
    )
    if not fetched.ok or not fetched.data:
        return DownloadResult(
            ok=False,
            path=None,
            size=0,
            sha256="",
            md5="",
            mime_type=mime_type or "",
            error=fetched.error or "Download failed",
            strategy=fetched.strategy,
        )

    digest = sha256_bytes(fetched.data)
    md5 = md5_bytes(fetched.data)
    path = write_fetched_bytes(
        settings,
        file_id=file_id,
        data=fetched.data,
        extension=fetched.extension or "bin",
        digest_prefix=digest[:12],
    )
    return DownloadResult(
        ok=True,
        path=path,
        size=len(fetched.data),
        sha256=digest,
        md5=md5,
        mime_type=fetched.mime_type or mime_type,
        strategy=fetched.strategy,
    )
