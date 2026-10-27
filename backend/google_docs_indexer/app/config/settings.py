"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the indexer."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Supabase
    supabase_url: str = Field(default="", description="Supabase project URL")
    supabase_key: str = Field(default="", description="Supabase API key")
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
        description="Async SQLAlchemy database URL",
    )

    # Crawler
    max_workers: int = Field(default=50, ge=1, le=200)
    download_timeout: float = Field(default=30.0, ge=5.0)
    rate_limit: float = Field(default=10.0, ge=0.1, description="Requests per second")
    user_agent: str = Field(
        default="GoogleDocsPublicIndexer/1.0 (+https://github.com/example/indexer)"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Paths
    log_dir: Path = Field(default=Path("logs"))
    data_dir: Path = Field(default=Path("data"))
    url_list_file: Path = Field(default=Path("data/discovered_urls.txt"))
    discovered_urls_file: Path = Field(default=Path("data/discovered_urls.txt"))

    # Export
    export_formats: str = Field(default="html,txt")

    # Web search discovery
    search_max_results: int = Field(default=50, ge=1, le=100)
    search_concurrency: int = Field(default=8, ge=1, le=30, description="Parallel search queries")
    google_cse_api_key: str = Field(default="", description="Google Custom Search API key")
    google_cse_id: str = Field(default="", description="Google Programmable Search Engine ID")
    bing_search_api_key: str = Field(default="", description="Bing Web Search API key")
    queries_file: Path = Field(default=Path("data/queries.txt"))

    # MongoDB / Supabase document storage (same as API backend)
    database_storage: str = Field(default="auto", description="mongodb, supabase, or auto")
    google_docs_storage: str = Field(default="auto", description="mongodb, supabase, or auto")
    mongodb_uri: str = Field(default="", description="MongoDB connection URI")
    mongodb_db_name: str = Field(default="outreach_console", description="MongoDB database name")

    @field_validator("log_dir", "data_dir", "url_list_file", "queries_file", "discovered_urls_file", mode="before")
    @classmethod
    def parse_path(cls, v: str | Path) -> Path:
        return Path(v)

    @property
    def export_format_list(self) -> list[str]:
        return [f.strip().lower() for f in self.export_formats.split(",") if f.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
