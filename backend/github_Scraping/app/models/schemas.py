from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.scraper.constants import DEFAULT_COUNTRIES, DEFAULT_DATE_BUCKETS, DEFAULT_FOLLOWER_BUCKETS


class ScrapeConfig(BaseModel):
    countries: list[str] = Field(default_factory=lambda: list(DEFAULT_COUNTRIES))
    max_per_location: int | None = None
    follower_buckets: list[str] = Field(default_factory=lambda: list(DEFAULT_FOLLOWER_BUCKETS))
    date_buckets: list[str] = Field(default_factory=lambda: list(DEFAULT_DATE_BUCKETS))
    join_date_start: str | None = None
    join_date_end: str | None = None
    search_sort: str = Field(default="joined", pattern="^(joined|followers|repositories)$")
    search_order: str = Field(default="desc", pattern="^(asc|desc)$")
    skip_recent_hours: int = 24
    email_only: bool = True
    use_email_search_hint: bool = True
    profile_workers: int = Field(default=6, ge=1, le=24)


class ScrapeStartRequest(BaseModel):
    config: ScrapeConfig


class ScrapeRunResponse(BaseModel):
    id: UUID
    status: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    total_users_found: int = 0
    current_country: str | None = None
    countries_completed: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    log_lines: list[dict[str, Any]] = Field(default_factory=list)
    rate_limit_remaining: int | None = None
    rate_limit_reset_at: datetime | None = None
    estimated_seconds_remaining: int | None = None
    last_error: str | None = None
    celery_task_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TokenCreate(BaseModel):
    token: str
    label: str = "default"
    notes: str | None = None
    is_active: bool = True


class TokenResponse(BaseModel):
    id: UUID
    label: str
    is_active: bool
    last_used_at: datetime | None = None
    rate_limit_remaining: int | None = None
    rate_limit_reset_at: datetime | None = None
    notes: str | None = None
    token_preview: str | None = None


class TokenToggle(BaseModel):
    is_active: bool


class ScheduleCreate(BaseModel):
    name: str
    cron_expression: str
    config: ScrapeConfig
    active: bool = True


class ScheduleResponse(BaseModel):
    id: UUID
    name: str
    cron_expression: str
    config: dict[str, Any]
    active: bool
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None


class UserListParams(BaseModel):
    page: int = 1
    page_size: int = 50
    search: str | None = None
    country: str | None = None
    followers_min: int | None = None
    followers_max: int | None = None
    created_after: str | None = None
    created_before: str | None = None


class DashboardStats(BaseModel):
    total_users: int
    active_runs: int
    last_run: ScrapeRunResponse | None = None
    active_tokens: int


class AppReleaseResponse(BaseModel):
    id: UUID
    version: str
    title: str
    description: str | None = None
    install_instructions: str | None = None
    file_name: str
    file_size: int
    content_type: str | None = None
    sha256: str | None = None
    is_example: bool = False
    download_count: int = 0
    created_at: datetime | None = None
    download_url: str | None = None


class AppReleasePublicResponse(BaseModel):
    version: str
    title: str
    description: str | None = None
    install_instructions: str | None = None
    file_name: str
    file_size: int
    download_url: str
