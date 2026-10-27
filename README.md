# Outreach Console

GitHub user scraping + Google Drive indexing, with a FastAPI API and Next.js admin UI. **MongoDB** is the primary database.

**Full run guide:** see [README-MANAGEMENT.md](./README-MANAGEMENT.md).

## Quick start (Windows)

```powershell
# 1) MongoDB (portable under .tools\mongodb, or any local mongod on :27017)
.\start-mongo.ps1

# 2) Schema (once)
python scripts\apply_mongodb_schema.py

# 3) API (:8000) + UI (:3001)
.\start-project.ps1 -Install   # first time
.\start-project.ps1            # later
```

- UI: http://127.0.0.1:3001  
- API docs: http://127.0.0.1:8000/docs  
- Stop: `.\stop-project.ps1 -CloseShellWindows`

## CLI scraper (optional)

Standalone scraper (still writes via Supabase env vars if set). Shares scraper code with the API package:

```bash
python scrape_github_users.py --target-countries US,India,UK --max-per-location 200
```

Prefer the **management UI** (`/scrape/new`) for day-to-day runs.

## Layout

| Path | Role |
|------|------|
| `backend/github_Scraping/` | FastAPI app |
| `backend/outreach_db/` | Mongo helpers |
| `backend/google_drive_*` | Drive DB + indexer |
| `frontend/` | Next.js console |
| `schema/mongodb/` | Mongo indexes (use apply script; do not run `.sql` in Mongo mode) |
