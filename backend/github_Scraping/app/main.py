"""FastAPI management API for GitHub scraper."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import (
    auth,
    enrich,
    google_docs,
    google_drive,
    oauth,
    schedule,
    scrape,
    search,
    tokens,
    users,
)
from app.services.process_lock import ProcessFileLock
from app.services.scheduler import check_due_schedules


def _ensure_avatars_dir() -> None:
    from app.services.database import use_mongodb

    if use_mongodb():
        get_settings().avatars_path.mkdir(parents=True, exist_ok=True)


settings = get_settings()
scheduler = BackgroundScheduler(timezone="UTC")
scheduler_lock = ProcessFileLock(Path(__file__).resolve().parents[1] / ".scheduler.lock")
log = logging.getLogger(__name__)


def _maybe_init_database_storage() -> None:
    try:
        from app.services.database import storage_label, use_mongodb

        if use_mongodb():
            from outreach_db.client import ensure_indexes, ping

            if ping():
                ensure_indexes()
                log.info("Application storage: MongoDB (%s)", storage_label())
            else:
                log.warning("MONGODB_URI set but MongoDB is not reachable")
            return
    except Exception as exc:
        log.warning("MongoDB init skipped: %s", exc)

    settings = get_settings()
    if not (settings.supabase_db_password or settings.supabase_database_url):
        return
    try:
        from app.services.google_docs_schema import apply_google_docs_schema, check_google_docs_schema

        status = check_google_docs_schema(
            supabase_url=settings.supabase_url,
            db_password=settings.supabase_db_password,
            database_url=settings.supabase_database_url,
        )
        if status.get("ok"):
            return
        result = apply_google_docs_schema(
            supabase_url=settings.supabase_url,
            db_password=settings.supabase_db_password,
            database_url=settings.supabase_database_url,
        )
        log.info("Auto-applied Google Docs Supabase schema: %s", result)
    except Exception as exc:
        log.warning("Google Docs Supabase schema auto-setup skipped: %s", exc)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _ensure_avatars_dir()
    _maybe_init_database_storage()
    scheduler_started = False
    if settings.api_enable_scheduler and scheduler_lock.acquire():
        scheduler.add_job(
            check_due_schedules,
            "interval",
            minutes=1,
            id="check_due_schedules",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=120,
        )
        scheduler.start()
        scheduler_started = True
        log.info("Scheduler started in API worker process")
    elif settings.api_enable_scheduler:
        log.info("Scheduler already owned by another API worker")
    else:
        log.info("Scheduler disabled by API_ENABLE_SCHEDULER=false")
    yield
    if scheduler_started:
        scheduler.shutdown(wait=False)
        scheduler_lock.release()


app = FastAPI(
    title="GitHub Scraper Management API",
    version="1.0.0",
    description="Control scraping runs, tokens, schedules, and user data.",
    lifespan=lifespan,
)

cors_kwargs: dict = {
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if settings.cors_allow_network:
    cors_kwargs["allow_origins"] = settings.cors_origin_list
    cors_kwargs["allow_origin_regex"] = settings.cors_network_regex
else:
    cors_kwargs["allow_origins"] = settings.cors_origin_list

app.add_middleware(CORSMiddleware, **cors_kwargs)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.exception_handler(Exception)
async def unhandled_exception(_request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled API error")
    detail = "Internal server error"
    return JSONResponse(status_code=500, content={"detail": detail})


app.include_router(auth.router)
app.include_router(google_docs.router)
app.include_router(google_docs.public_router)
app.include_router(google_drive.router)
app.include_router(google_drive.public_router)
app.include_router(search.router)
app.include_router(scrape.router)
app.include_router(users.router)
app.include_router(enrich.router)
app.include_router(tokens.router)
app.include_router(schedule.router)
app.include_router(oauth.router)


@app.get("/health")
async def health() -> dict:
    from app.services.database import storage_label, use_mongodb

    payload: dict = {"status": "ok", "storage": storage_label()}
    if use_mongodb():
        from outreach_db.client import ping

        payload["mongodb"] = "connected" if ping() else "unreachable"
        payload["auth"] = "mongodb"
    else:
        payload["auth"] = "supabase"
    return payload
