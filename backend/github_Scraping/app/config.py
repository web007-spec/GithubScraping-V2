from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    auth_jwt_secret: str = ""

    token_encryption_key: str = ""

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 2
    api_enable_scheduler: bool = True
    cors_origins: str = "http://localhost:3001"
    # Allow browsers from other PCs on your LAN (private IPs + localhost)
    cors_allow_network: bool = True

    admin_role: str = "admin"

    # Allow new users to register via the UI and become admin
    allow_public_registration: bool = True
    # If set, the registration form must include this secret
    registration_secret: str = ""

    openai_api_key: str = ""
    gemini_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    gemini_model: str = "gemini-2.0-flash"

    # AI search (OpenAI-first, token-efficient)
    ai_search_provider: str = "openai"
    ai_search_llm_top_n: int = 14
    ai_search_skip_llm_min_score: int = 93
    ai_search_cache_ttl_sec: int = 600
    ai_search_min_result_score: int = 65

    google_client_id: str = ""
    google_client_secret: str = ""

    avatars_dir: str = "avatars"
    avatar_max_bytes: int = 2 * 1024 * 1024  # 2 MB

    # Direct Postgres password for one-time schema migrations (Dashboard → Database)
    supabase_db_password: str = ""
    supabase_database_url: str = ""

    # Database storage: auto (MongoDB if MONGODB_URI set, else Supabase)
    mongodb_uri: str = ""
    mongodb_db_name: str = "outreach_console"
    database_storage: str = "auto"
    # Legacy alias for Google Docs only
    google_docs_storage: str = "auto"

    # Regex for LAN / local access when cors_allow_network is enabled
    cors_network_regex: str = (
        r"https?://("
        r"localhost|127\.0\.0\.1|"
        r"192\.168\.\d{1,3}\.\d{1,3}|"
        r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
        r")(:\d+)?"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def avatars_path(self) -> Path:
        root = Path(__file__).resolve().parents[2]
        return (root / self.avatars_dir).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
