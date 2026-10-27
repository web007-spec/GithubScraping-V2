"""Settings for the Public Google Drive Indexer."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parents[1]
_ENV = _ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV), extra="ignore")

    mongo_uri: str = ""
    mongo_db_name: str = "outreach_console"
    database_storage: str = "mongodb"

    download_path: Path = Path("downloads")
    thumbnail_path: Path = Path("thumbnails")
    cache_path: Path = Path("cache")
    log_path: Path = Path("logs")

    max_file_size_mb: int = 50
    max_concurrent_requests: int = 8
    request_delay_sec: float = 0.35
    max_retries: int = 4
    user_agent: str = (
        "Mozilla/5.0 (compatible; PublicDriveIndexer/1.0; +https://localhost/public-drive)"
    )

    enable_thumbnails: bool = True
    enable_ocr: bool = False
    workers: int = 6

    data_dir: Path = Path("data")
    queries_file: Path = Path("data/queries.txt")
    discovered_urls_file: Path = Path("data/discovered_urls.txt")
    search_max_results: int = 50
    search_concurrency: int = 8

    @property
    def max_file_size_bytes(self) -> int:
        return max(1, self.max_file_size_mb) * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    import os

    s = Settings()
    if not s.mongo_uri:
        s.mongo_uri = (
            os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI") or ""
        ).strip()
    if not s.mongo_db_name:
        s.mongo_db_name = (
            os.environ.get("MONGODB_DB_NAME") or "outreach_console"
        ).strip()
    root = _ROOT
    for path_attr in ("download_path", "thumbnail_path", "cache_path", "log_path", "data_dir"):
        p = getattr(s, path_attr)
        if isinstance(p, Path) and not p.is_absolute():
            p = root / p
            setattr(s, path_attr, p)
        if isinstance(p, Path):
            p.mkdir(parents=True, exist_ok=True)
    if not s.queries_file.is_absolute():
        s.queries_file = root / s.queries_file
    if not s.discovered_urls_file.is_absolute():
        s.discovered_urls_file = root / s.discovered_urls_file
    return s
